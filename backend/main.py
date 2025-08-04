import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import praw
from concurrent.futures import ThreadPoolExecutor
from prawcore.exceptions import ServerError, ResponseException

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# CORS middleware so frontend can access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Reddit API credentials securely from environment variables
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "WallStreetBetsSentimentApp by rt")

if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
    raise RuntimeError("Reddit API credentials not set in environment variables")

# Initialize Reddit API client
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

# Initialize VADER sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(text: str) -> float:
    """
    Returns compound sentiment score (-1 to +1) of the input text.
    """
    if not text.strip():
        return 0.0
    scores = analyzer.polarity_scores(text)
    return scores["compound"]

def fetch_submission_with_retry(url: str, retries: int = 3, delay: int = 5):
    for attempt in range(retries):
        try:
            submission = reddit.submission(url=url)
            _ = submission.id  # Access id to trigger fetching and validation
            return submission
        except (ServerError, ResponseException) as e:
            # Check if it's a rate limit (HTTP 429)
            if hasattr(e, 'response') and e.response.status_code == 429:
                print(f"Rate limit exceeded, sleeping for {delay}s (attempt {attempt+1}/{retries})")
                time.sleep(delay)
            else:
                raise HTTPException(status_code=400, detail=f"Error fetching submission: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error fetching submission: {str(e)}")

    raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")

@app.get("/analyze_post")
def analyze_reddit_post(
    url: str = Query(..., description="Full Reddit post URL to analyze"),
    max_comments: int = Query(100, ge=1, le=500, description="Max number of top-level comments to analyze")
):
    """
    Analyzes sentiment of a Reddit post and its top-level comments.
    Returns JSON with post info and comments including sentiment scores.
    """
    # Relaxed URL validation
    if "reddit.com" not in url.lower():
        raise HTTPException(status_code=400, detail="Invalid Reddit post URL")

    # Fetch Reddit submission with retry logic on rate limits
    submission = fetch_submission_with_retry(url)

    # Analyze sentiment of post title + selftext
    submission_text = f"{submission.title} {submission.selftext}"
    post_sentiment = analyze_sentiment(submission_text)

    # Load comments, avoid excessive API calls
    submission.comments.replace_more(limit=0)

    # Extract top-level comments
    top_level_comments = [c for c in submission.comments if isinstance(c, praw.models.Comment)]

    # Limit comments for performance
    top_level_comments = top_level_comments[:max_comments]

    def analyze_comment(comment):
        return {
            "id": comment.id,
            "body": comment.body,
            "sentiment": analyze_sentiment(comment.body),
            "score": comment.score,
            "author": str(comment.author),
            "created_utc": comment.created_utc
        }

    # Parallelize comment sentiment analysis
    with ThreadPoolExecutor(max_workers=10) as executor:
        comments_data = list(executor.map(analyze_comment, top_level_comments))

    # Return comprehensive JSON response
    return {
        "id": submission.id,
        "title": submission.title,
        "selftext": submission.selftext,
        "sentiment": post_sentiment,
        "score": submission.score,
        "url": submission.url,
        "num_comments": submission.num_comments,
        "created_utc": submission.created_utc,
        "top_comments": comments_data
    }
