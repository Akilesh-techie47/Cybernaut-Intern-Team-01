import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from app.config.settings import config
import logging

logger = logging.getLogger(__name__)

_analyzer = None


def get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s\.\,\!\?\-\'\"]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def analyze_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return {"label": "neutral", "score": 0.0, "compound": 0.0}

    analyzer = get_analyzer()
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]

    cfg = config[__import__("os").getenv("FLASK_ENV", "default")]
    pos_threshold = cfg.SENTIMENT_POSITIVE_THRESHOLD
    neg_threshold = cfg.SENTIMENT_NEGATIVE_THRESHOLD

    if compound >= pos_threshold:
        label = "positive"
    elif compound <= neg_threshold:
        label = "negative"
    else:
        label = "neutral"

    return {
        "label": label,
        "score": compound,
        "compound": compound,
        "positive": scores["pos"],
        "negative": scores["neg"],
        "neutral": scores["neu"],
    }


def batch_analyze(texts: list) -> list:
    return [analyze_sentiment(t) for t in texts]


def get_sentiment_label(score: float) -> str:
    cfg = config[__import__("os").getenv("FLASK_ENV", "default")]
    if score >= cfg.SENTIMENT_POSITIVE_THRESHOLD:
        return "positive"
    elif score <= cfg.SENTIMENT_NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"