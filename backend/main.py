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

analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text: str) -> float:
    if not text.strip():
        return 0.0
    return analyzer.polarity_scores(text)["compound"]

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

    submission_text = f"{submission.title} {submission.selftext}"
    post_sentiment = analyze_sentiment(submission_text)

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

    return {
        "id": submission.id,
        "title": submission.title,
        "selftext": submission.selftext,
        "sentiment": post_sentiment,
        "score": submission.score,
        "url": submission.url,
        "num_comments": submission.num_comments,
        "created_utc": submission.created_utc,
        "top_comments": comments_data,
    }
