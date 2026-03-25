from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_PIPELINE: Any | None = None
_PIPELINE_LOCK = threading.Lock()
_PH_HINT_TOKENS: set[str] | None = None
_PH_HINT_LOCK = threading.Lock()

_REPORTING_PREFIX_RE = re.compile(
    r"^\s*(according to|as of now|as of today|as of|reported|confirmed|update|tip)\s*(?:[:\\-–—]\\s*)?",
    flags=re.IGNORECASE,
)

# Small set of high-signal English sentiment tokens to avoid neutralizing
# genuinely emotional/violent reporting headlines.
_EN_SENTIMENT_HINTS = {
    "kill",
    "killed",
    "dead",
    "dies",
    "died",
    "murder",
    "rape",
    "raped",
    "scam",
    "fraud",
    "arrest",
    "arrested",
    "attack",
    "attacked",
    "bomb",
    "explosion",
    "crash",
    "accident",
    "injured",
    "injury",
    "fatal",
    "worst",
    "best",
    "great",
    "terrible",
    "awful",
    "hate",
    "love",
}


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in {"1", "true", "t", "yes", "y", "on"}


def _get_env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v > 0 else default
    except Exception:
        return default


def _get_env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _load_ph_hint_tokens() -> set[str]:
    """
    Load PH lexicon keys as a cheap "sentiment-hint" vocabulary.
    Used only for lightweight heuristic checks (no VADER import).
    """
    global _PH_HINT_TOKENS
    if _PH_HINT_TOKENS is not None:
        return _PH_HINT_TOKENS
    with _PH_HINT_LOCK:
        if _PH_HINT_TOKENS is not None:
            return _PH_HINT_TOKENS
        try:
            here = os.path.dirname(__file__)
            path = os.path.join(here, "vader_ph_lexicon.v1.json")
            import json

            payload = json.load(open(path, "r", encoding="utf-8")) or {}
            lex = payload.get("lexicon") or {}
            tokens = set()
            for k, v in lex.items():
                if not isinstance(k, str) or not k.strip() or not isinstance(v, (int, float)):
                    continue
                # Keep moderately strong terms only (avoid flooding with weak slang).
                if abs(float(v)) >= 1.2:
                    tokens.add(k.strip().lower())
            _PH_HINT_TOKENS = tokens
        except Exception:
            _PH_HINT_TOKENS = set()
        return _PH_HINT_TOKENS


def _looks_like_reporting_preface(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_REPORTING_PREFIX_RE.match(raw))


def _should_neutralize_reporting(text: str) -> bool:
    """
    DistilBERT SST-2 is binary and often over-polarizes "reporting preface" text.
    If the text looks like a neutral preface and contains no strong sentiment hints,
    short-circuit to neutral.
    """
    if not _truthy_env("DISTILBERT_NEUTRALIZE_REPORTING") and os.getenv("DISTILBERT_NEUTRALIZE_REPORTING") is not None:
        return False
    if not _looks_like_reporting_preface(text):
        return False

    tail = _REPORTING_PREFIX_RE.sub("", (text or "").strip(), count=1).strip(" \t-:—")
    tokens = re.findall(r"[a-zñ]+", tail.lower(), flags=re.IGNORECASE)
    if not tokens:
        return True

    ph_hints = _load_ph_hint_tokens()
    for t in tokens:
        if t in _EN_SENTIMENT_HINTS:
            return False
        if t in ph_hints:
            return False
    return True


def _get_pipeline() -> Any:
    """
    Lazily construct the Hugging Face pipeline once per process.
    Safe for Celery prefork (each worker process builds its own singleton).
    """
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    with _PIPELINE_LOCK:
        if _PIPELINE is not None:
            return _PIPELINE

        model_id = (os.getenv("DISTILBERT_MODEL_ID") or "").strip() or "distilbert-base-uncased-finetuned-sst-2-english"
        local_only = _truthy_env("TRANSFORMERS_OFFLINE") or _truthy_env("HF_HUB_OFFLINE")
        hf_home = (os.getenv("HF_HOME") or "").strip()
        cache_dir_candidates: list[str | None] = [None]
        if hf_home:
            # Some tools write under HF_HOME directly, others under HF_HOME/hub.
            cache_dir_candidates.extend([hf_home, os.path.join(hf_home, "hub")])

        # Safer defaults on flaky networks (env vars can override).
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"transformers is not installed: {e}") from e

        # Tokenizer/model can land in different cache roots depending on how they were downloaded.
        # Try default HF cache first, then fall back to cache_dir=HF_HOME.
        #
        # Some partial downloads contain only `vocab.txt` + `tokenizer_config.json` but not
        # `tokenizer.json`. In that case, fast tokenizers can fail; fall back to slow.
        tokenizer = None
        tok_errors: list[str] = []
        for use_fast in (True, False):
            for cache_dir in cache_dir_candidates:
                try:
                    tokenizer = AutoTokenizer.from_pretrained(
                        model_id,
                        local_files_only=local_only,
                        cache_dir=cache_dir,
                        use_fast=use_fast,
                    )
                    break
                except Exception as e:
                    tok_errors.append(str(e))
                    tokenizer = None
            if tokenizer is not None:
                break
        if tokenizer is None:
            raise RuntimeError(f"Can't load tokenizer for '{model_id}': {' | '.join(tok_errors[-2:])}")

        model = None
        model_errors: list[str] = []
        for cache_dir in cache_dir_candidates:
            try:
                model = AutoModelForSequenceClassification.from_pretrained(
                    model_id,
                    local_files_only=local_only,
                    cache_dir=cache_dir,
                )
                break
            except Exception as e:
                model_errors.append(str(e))
                model = None
        if model is None:
            raise RuntimeError(f"Can't load model for '{model_id}': {' | '.join(model_errors[-2:])}")
        _PIPELINE = pipeline(task="sentiment-analysis", model=model, tokenizer=tokenizer, device=-1)
        return _PIPELINE


def analyze_sentiment_distilbert_detailed(text: str) -> tuple[float, str, float, dict[str, Any]]:
    """
    DistilBERT SST-2 sentiment on CPU.

    Returns: (compound_score, label, elapsed_ms, metadata)
      - compound_score in [-1, 1] (POSITIVE => +score, NEGATIVE => -score)
      - label in {positive|neutral|negative}

    Env:
      - DISTILBERT_MODEL_ID (default: distilbert-base-uncased-finetuned-sst-2-english)
      - DISTILBERT_MAX_LENGTH (default: 512 tokens)
      - DISTILBERT_MAX_CHARS (default: 2000 chars)
      - DISTILBERT_NEUTRAL_MIN_CONF (default: 0.60)
    """
    start = time.time()
    raw = (text or "").strip()

    model_id = (os.getenv("DISTILBERT_MODEL_ID") or "").strip() or "distilbert-base-uncased-finetuned-sst-2-english"
    max_length = _get_env_int("DISTILBERT_MAX_LENGTH", 512)
    max_chars = _get_env_int("DISTILBERT_MAX_CHARS", 2000)
    neutral_min_conf = _get_env_float("DISTILBERT_NEUTRAL_MIN_CONF", 0.60)

    clipped = raw[:max_chars]
    truncated_chars = max(0, len(raw) - len(clipped))

    if not clipped:
        elapsed_ms = (time.time() - start) * 1000.0
        return 0.0, "neutral", elapsed_ms, {
            "library": "hf-transformers",
            "engine": "distilbert_sst2",
            "transformer_model_id": model_id,
            "max_length": max_length,
            "max_chars": max_chars,
            "neutral_min_conf": neutral_min_conf,
            "truncated_chars": truncated_chars,
            "transformer_label_raw": None,
            "transformer_score_raw": None,
            "error": None,
        }

    if _should_neutralize_reporting(clipped):
        elapsed_ms = (time.time() - start) * 1000.0
        return 0.0, "neutral", elapsed_ms, {
            "library": "hf-transformers",
            "engine": "distilbert_sst2",
            "transformer_model_id": model_id,
            "max_length": max_length,
            "max_chars": max_chars,
            "neutral_min_conf": neutral_min_conf,
            "truncated_chars": truncated_chars,
            "transformer_label_raw": None,
            "transformer_score_raw": None,
            "neutralized_reporting_preface": True,
            "error": None,
        }

    try:
        pipe = _get_pipeline()
        out = pipe(clipped, truncation=True, max_length=max_length)
        item = out[0] if isinstance(out, list) and out else (out or {})

        label_raw = str((item or {}).get("label") or "").upper()
        score_raw = float((item or {}).get("score") or 0.0)

        is_positive = "POS" in label_raw
        base_label = "positive" if is_positive else "negative"
        compound = score_raw if is_positive else -score_raw

        label = base_label
        if score_raw < neutral_min_conf:
            label = "neutral"
            compound = 0.0

        elapsed_ms = (time.time() - start) * 1000.0
        return compound, label, elapsed_ms, {
            "library": "hf-transformers",
            "engine": "distilbert_sst2",
            "transformer_model_id": model_id,
            "max_length": max_length,
            "max_chars": max_chars,
            "neutral_min_conf": neutral_min_conf,
            "truncated_chars": truncated_chars,
            "transformer_label_raw": label_raw,
            "transformer_score_raw": score_raw,
            "label_unthresholded": base_label,
            "compound_unthresholded": (score_raw if is_positive else -score_raw),
            "error": None,
        }
    except Exception as e:
        logger.warning("DistilBERT sentiment failed; returning neutral: %s", e)
        elapsed_ms = (time.time() - start) * 1000.0
        return 0.0, "neutral", elapsed_ms, {
            "library": "hf-transformers",
            "engine": "distilbert_sst2",
            "transformer_model_id": model_id,
            "max_length": max_length,
            "max_chars": max_chars,
            "neutral_min_conf": neutral_min_conf,
            "truncated_chars": truncated_chars,
            "transformer_label_raw": None,
            "transformer_score_raw": None,
            "error": str(e),
        }
