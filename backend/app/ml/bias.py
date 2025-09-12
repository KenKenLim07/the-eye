import time
from typing import Tuple, Dict, Any

# Lazy NLTK/VADER import and resource bootstrap
_vader = None


def _ensure_vader():
    global _vader
    if _vader is not None:
        return _vader
    try:
        from nltk.sentiment import SentimentIntensityAnalyzer
        try:
            # Try to construct; if lexicon missing, download
            _vader = SentimentIntensityAnalyzer()
            return _vader
        except Exception:
            import nltk
            nltk.download('vader_lexicon', quiet=True)
            _vader = SentimentIntensityAnalyzer()
            return _vader
    except Exception as e:
        raise RuntimeError(f"Failed to initialize VADER: {e}")


def analyze_sentiment_vader(text: str) -> Tuple[float, str, float]:
    """
    Returns: (compound_score, label, elapsed_ms)
    compound_score in [-1, 1]
    label in {positive|neutral|negative}
    """
    start = time.time()
    sia = _ensure_vader()
    scores = sia.polarity_scores(text or "")
    compound = float(scores.get("compound", 0.0))
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    elapsed_ms = (time.time() - start) * 1000.0
    return compound, label, elapsed_ms


def build_bias_row_for_vader(article_id: int, text: str) -> Dict[str, Any]:
    compound, label, elapsed_ms = analyze_sentiment_vader(text)
    return {
        "article_id": article_id,
        "model_version": "vader_v1",
        "model_type": "sentiment",
        "sentiment_score": compound,
        "sentiment_label": label,
        "confidence_score": None,
        "processing_time_ms": int(elapsed_ms),
        "model_metadata": {"library": "nltk-vader", "threshold_pos": 0.05, "threshold_neg": -0.05},
    } 