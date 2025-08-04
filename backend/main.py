import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import praw
from concurrent.futures import ThreadPoolExecutor
from prawcore.exceptions import ServerError, ResponseException

load_dotenv()

app = FastAPI()

# Allow frontend localhost CORS access (adjust origins in production!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "WallStreetBetsSentimentApp by rt")

if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
    raise RuntimeError("Missing Reddit API credentials in env")

reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)

# Load your custom lexicon file with phrases using underscores for multi-word
def load_custom_lexicon(file_path: str) -> dict:
    lex = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            # The last part is the score, the rest is the token (handles tokens with spaces)
            score = float(parts[-1])
            token = "_".join(parts[:-1]).lower()  # join multi-word tokens with underscores
            lex[token] = score
    return lex

# Path to your custom lexicon txt file (adjust if needed)
LEXICON_PATH = "custom_lexicon.txt"
custom_lexicon = load_custom_lexicon(LEXICON_PATH)

analyzer = SentimentIntensityAnalyzer()
analyzer.lexicon = custom_lexicon  # replace VADER's default lexicon with yours

# List of multi-word phrases from your lexicon to preprocess in input text
multi_word_phrases = [k for k in custom_lexicon if "_" in k]

def preprocess_text(text: str) -> str:
    text = text.lower()
    for phrase in multi_word_phrases:
        # Replace underscores with spaces for searching
        phrase_spaced = phrase.replace("_", " ")
        text = text.replace(phrase_spaced, phrase)
    return text

def analyze_sentiment(text: str) -> float:
    if not text.strip():
        return 0.0
    processed_text = preprocess_text(text)
    return analyzer.polarity_scores(processed_text)["compound"]

def fetch_submission_with_retry(url: str, retries=3, delay=5):
    for attempt in range(retries):
        try:
            submission = reddit.submission(url=url)
            _ = submission.id  # force fetch
            return submission
        except (ServerError, ResponseException) as e:
            if hasattr(e, "response") and e.response.status_code == 429:
                time.sleep(delay)
            else:
                raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=429, detail="Rate limit exceeded, try later")

@app.get("/analyze_post")
def analyze_reddit_post(
    url: str = Query(..., description="Full Reddit post URL"),
    max_comments: int = Query(100, ge=1, le=500, description="Max top-level comments to analyze"),
):
    if "reddit.com" not in url.lower():
        raise HTTPException(status_code=400, detail="Invalid Reddit URL")

    submission = fetch_submission_with_retry(url)

    submission.comments.replace_more(limit=0)
    top_level_comments = [c for c in submission.comments if isinstance(c, praw.models.Comment)]
    top_level_comments = top_level_comments[:max_comments]

    def analyze_comment(comment):
        return {
            "id": comment.id,
            "body": comment.body,
            "sentiment": analyze_sentiment(comment.body),
            "score": comment.score,
            "author": str(comment.author),
            "created_utc": comment.created_utc,
        }

    with ThreadPoolExecutor(max_workers=10) as executor:
        comments_data = list(executor.map(analyze_comment, top_level_comments))

    # Calculate overall sentiment as average of comment sentiments
    if comments_data:
        overall_sentiment = sum(c["sentiment"] for c in comments_data) / len(comments_data)
    else:
        overall_sentiment = 0.0

    return {
        "id": submission.id,
        "title": submission.title,
        "selftext": submission.selftext,
        "sentiment": overall_sentiment,
        "score": submission.score,
        "url": submission.url,
        "num_comments": submission.num_comments,
        "created_utc": submission.created_utc,
        "top_comments": comments_data,
    }
