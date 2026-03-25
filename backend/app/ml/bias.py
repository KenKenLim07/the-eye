import time
from typing import Tuple, Dict, Any
import json
import os
import re
import logging

# Lazy NLTK/VADER import and resource bootstrap
_vader = None
_VADER_PH_PATCH_CACHE: dict[str, Any] | None = None
_VADER_PH_PATCH_APPLIED: bool = False
_VADER_PH_PATCH_ERROR: str | None = None
_VADER_PH_PATCH_STATUS_CACHE: dict[str, Any] | None = None

logger = logging.getLogger(__name__)

_LABEL_THRESHOLDS_CACHE: tuple[float, float] | None = None


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in {"1", "true", "t", "yes", "y", "on"}


def _load_vader_ph_patch() -> dict[str, Any]:
    global _VADER_PH_PATCH_CACHE
    if _VADER_PH_PATCH_CACHE is not None:
        return _VADER_PH_PATCH_CACHE
    path = os.path.join(os.path.dirname(__file__), "vader_ph_lexicon.v1.json")
    with open(path, "r", encoding="utf-8") as f:
        _VADER_PH_PATCH_CACHE = json.load(f) or {}
    return _VADER_PH_PATCH_CACHE


def _compile_phrase_patterns(phrases: dict[str, Any]) -> list[tuple[re.Pattern[str], str]]:
    """
    Return a list of (regex_pattern, replacement_token) pairs.
    We match phrases case-insensitively with conservative word-ish boundaries.
    """
    compiled: list[tuple[re.Pattern[str], str]] = []
    if not phrases:
        return compiled

    # Replace longer phrases first to avoid partial overlaps.
    for phrase in sorted(phrases.keys(), key=lambda s: len(s), reverse=True):
        meta = phrases.get(phrase) or {}
        token = str(meta.get("token") or "").strip()
        if not phrase or not token:
            continue
        # Phrase boundaries: avoid replacing inside alphanumeric runs.
        pat = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
        compiled.append((pat, token))
    return compiled


def _preprocess_for_vader(text: str) -> str:
    """
    Minimal deterministic preprocessing:
    - Apply configured multi-word phrase substitutions (e.g. "sana all" -> "sanaall")
    - Normalize Tagalog contrast words (e.g. "pero") to English "but" so VADER's
      built-in contrast weighting reliably triggers.
    This runs only when the PH patch is enabled and loaded.
    """
    raw = text or ""
    if not raw:
        return raw
    try:
        patch = _load_vader_ph_patch()
        phrases = patch.get("phrases") or {}
        patterns = patch.get("_compiled_phrase_patterns")  # cached on patch dict
        if patterns is None:
            patterns = _compile_phrase_patterns(phrases)
            patch["_compiled_phrase_patterns"] = patterns
        for pat, token in patterns:
            raw = pat.sub(token, raw)

        # Normalize Tagalog contrast conjunctions to "but" (word-boundary match).
        # Even if we also patch VADER's BUT_WORDS, this makes behavior consistent.
        but_words = patch.get("but_words") or []
        contrast_pat = patch.get("_compiled_contrast_pattern")
        if contrast_pat is None and but_words:
            ws = [re.escape(str(w).strip()) for w in but_words if str(w).strip()]
            if ws:
                contrast_pat = re.compile(rf"(?<!\w)({'|'.join(ws)})(?!\w)", re.IGNORECASE)
                patch["_compiled_contrast_pattern"] = contrast_pat
            else:
                patch["_compiled_contrast_pattern"] = False
                contrast_pat = None
        if contrast_pat:
            raw = contrast_pat.sub("but", raw)
        return raw
    except Exception:
        # Fail closed: keep original text on patch issues.
        return raw


def _get_label_thresholds(
    *, default_pos: float = 0.05, default_neg: float = -0.05
) -> tuple[float, float]:
    """
    Allow tuning sentiment label thresholds without changing code.

    Env:
      - VADER_NEUTRAL_BAND: numeric, e.g. 0.12 => pos>=0.12, neg<=-0.12
    """
    global _LABEL_THRESHOLDS_CACHE
    if _LABEL_THRESHOLDS_CACHE is not None:
        return _LABEL_THRESHOLDS_CACHE

    pos, neg = float(default_pos), float(default_neg)
    try:
        band_raw = (os.getenv("VADER_NEUTRAL_BAND") or "").strip()
        if band_raw:
            band = abs(float(band_raw))
            if band > 0:
                pos, neg = band, -band
    except Exception:
        pos, neg = float(default_pos), float(default_neg)

    _LABEL_THRESHOLDS_CACHE = (pos, neg)
    return _LABEL_THRESHOLDS_CACHE


def _apply_vader_ph_patch(sia: Any) -> dict[str, Any]:
    """
    Best-effort Taglish patch for VADER.
    Applies once per process when VADER_PH_PATCH is truthy.
    Returns patch status info for metadata.
    """
    global _VADER_PH_PATCH_APPLIED, _VADER_PH_PATCH_ERROR, _VADER_PH_PATCH_STATUS_CACHE
    enabled = _truthy_env("VADER_PH_PATCH")
    status: dict[str, Any] = {
        "ph_patch_enabled": enabled,
        "ph_patch_applied": False,
        "ph_patch_version": None,
        "ph_lexicon_terms_added": 0,  # number of NEW tokens added (not overrides)
        "ph_lexicon_overrides": 0,  # number of tokens that replaced existing VADER entries (allowlisted only)
        "ph_lexicon_skipped_existing": 0,  # collisions skipped because not allowlisted
        "ph_negations_added": 0,
        "ph_boosters_added": 0,
        "ph_but_words_added": 0,
        "ph_phrases_enabled": 0,
        "ph_patch_error": None,
    }

    if not enabled:
        return status

    if _VADER_PH_PATCH_APPLIED:
        # Already applied in this process; return cached status so metadata stays stable.
        if _VADER_PH_PATCH_STATUS_CACHE is not None:
            return dict(_VADER_PH_PATCH_STATUS_CACHE)
        status["ph_patch_applied"] = True
        status["ph_patch_error"] = _VADER_PH_PATCH_ERROR
        try:
            patch = _load_vader_ph_patch()
            status["ph_patch_version"] = patch.get("version")
            phrases = patch.get("phrases") or {}
            status["ph_phrases_enabled"] = len(phrases)
        except Exception:
            pass
        return status

    try:
        patch = _load_vader_ph_patch()
        status["ph_patch_version"] = patch.get("version")

        lexicon = patch.get("lexicon") or {}
        phrases = patch.get("phrases") or {}
        negations = patch.get("negations") or []
        boosters = patch.get("boosters") or {}
        but_words = patch.get("but_words") or []
        override_existing_allowlist = patch.get("override_existing_allowlist") or []
        allow_override_set = {str(x).strip().lower() for x in override_existing_allowlist if str(x).strip()}

        # Phrase tokens must be present in the lexicon for VADER to score them.
        phrase_lex = {}
        for _phrase, meta in phrases.items():
            token = str((meta or {}).get("token") or "").strip()
            val = (meta or {}).get("valence")
            if token and isinstance(val, (int, float)):
                phrase_lex[token] = float(val)

        merged_lex = {}
        for k, v in {**lexicon, **phrase_lex}.items():
            if isinstance(k, str) and k and isinstance(v, (int, float)):
                merged_lex[k] = float(v)

        if merged_lex:
            base_lex = getattr(sia, "lexicon", {}) or {}
            filtered: dict[str, float] = {}
            additions = 0
            overrides = 0
            skipped = 0
            for token, val in merged_lex.items():
                token_l = token.lower()
                if token in base_lex and token_l not in allow_override_set:
                    skipped += 1
                    continue
                filtered[token] = float(val)
                if token in base_lex:
                    overrides += 1
                else:
                    additions += 1

            if filtered:
                sia.lexicon.update(filtered)

            status["ph_lexicon_terms_added"] = additions
            status["ph_lexicon_overrides"] = overrides
            status["ph_lexicon_skipped_existing"] = skipped

        status["ph_phrases_enabled"] = len(phrases)

        # Optional VADER constant tweaks (guarded; NLTK internals may change).
        constants = getattr(sia, "constants", None)
        if constants is not None:
            # Negations
            if hasattr(constants, "NEGATE") and isinstance(negations, list):
                before = len(constants.NEGATE)
                constants.NEGATE.update({str(x).strip().lower() for x in negations if str(x).strip()})
                status["ph_negations_added"] = max(0, len(constants.NEGATE) - before)

            # Boosters/dampeners
            if hasattr(constants, "BOOSTER_DICT") and isinstance(boosters, dict):
                before = len(constants.BOOSTER_DICT)
                for k, v in boosters.items():
                    if not isinstance(k, str) or not k.strip() or not isinstance(v, (int, float)):
                        continue
                    constants.BOOSTER_DICT[k.strip().lower()] = float(v)
                status["ph_boosters_added"] = max(0, len(constants.BOOSTER_DICT) - before)

            # "but" equivalents (Tagalog)
            if hasattr(constants, "BUT_WORDS") and isinstance(but_words, list) and but_words:
                try:
                    before = len(constants.BUT_WORDS)
                except Exception:
                    before = 0
                to_add = {str(x).strip().lower() for x in but_words if str(x).strip()}
                if to_add and isinstance(constants.BUT_WORDS, (set, list, tuple)):
                    try:
                        if isinstance(constants.BUT_WORDS, set):
                            constants.BUT_WORDS.update(to_add)
                        else:
                            bw = set(constants.BUT_WORDS)
                            bw.update(to_add)
                            constants.BUT_WORDS = list(bw)
                    except Exception:
                        pass
                try:
                    status["ph_but_words_added"] = max(0, len(constants.BUT_WORDS) - before)
                except Exception:
                    status["ph_but_words_added"] = 0

        _VADER_PH_PATCH_APPLIED = True
        _VADER_PH_PATCH_ERROR = None
        status["ph_patch_applied"] = True
        _VADER_PH_PATCH_STATUS_CACHE = dict(status)
        return status

    except Exception as e:
        _VADER_PH_PATCH_APPLIED = True  # prevent repeated attempts spamming logs
        _VADER_PH_PATCH_ERROR = str(e)
        status["ph_patch_error"] = str(e)
        _VADER_PH_PATCH_STATUS_CACHE = dict(status)
        logger.warning("VADER PH patch failed; continuing without patch: %s", e)
        return status


def _ensure_vader():
    global _vader
    if _vader is not None:
        return _vader
    try:
        from nltk.sentiment import SentimentIntensityAnalyzer
        try:
            # Try to construct; if lexicon missing, download
            _vader = SentimentIntensityAnalyzer()
            _apply_vader_ph_patch(_vader)
            return _vader
        except Exception:
            import nltk
            nltk.download('vader_lexicon', quiet=True)
            _vader = SentimentIntensityAnalyzer()
            _apply_vader_ph_patch(_vader)
            return _vader
    except Exception as e:
        raise RuntimeError(f"Failed to initialize VADER: {e}")


# Existing sentiment analysis

def _label_from_compound(compound: float, pos_threshold: float = 0.05, neg_threshold: float = -0.05) -> str:
    # If the caller uses defaults, allow env-driven tuning.
    if pos_threshold == 0.05 and neg_threshold == -0.05:
        pos_threshold, neg_threshold = _get_label_thresholds(default_pos=pos_threshold, default_neg=neg_threshold)
    if compound >= pos_threshold:
        return "positive"
    if compound <= neg_threshold:
        return "negative"
    return "neutral"


def _split_long_text_chunks(text: str, max_chunk_chars: int = 700) -> tuple[str, list[str]]:
    """Split long news text into title + body chunks for weighted VADER aggregation."""
    raw = (text or "").strip()
    if not raw:
        return "", []

    # Prefer explicit title/body split when caller provides "\n\n" separator.
    blocks = [b.strip() for b in re.split(r"\n{2,}", raw) if b and b.strip()]
    if len(blocks) >= 2:
        title = blocks[0]
        body_text = "\n\n".join(blocks[1:])
    else:
        title = blocks[0] if blocks else ""
        body_text = ""

    # Sentence-level segmentation as base unit for chunking.
    sentence_source = body_text if body_text else raw
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", sentence_source) if s and s.strip()]
    if not sentences:
        return title, []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for s in sentences:
        slen = len(s)
        if current and (current_len + slen + 1) > max_chunk_chars:
            chunks.append(" ".join(current))
            current = [s]
            current_len = slen
        else:
            current.append(s)
            current_len += slen + (1 if current else 0)
    if current:
        chunks.append(" ".join(current))
    return title, chunks


def analyze_sentiment_vader_detailed(text: str) -> Tuple[float, str, float, Dict[str, Any]]:
    """
    Long-form VADER scoring for news:
    - score title, lead, and body chunks
    - aggregate with fixed weights to reduce long-text dilution
    """
    start = time.time()
    sia = _ensure_vader()
    patch_status = _apply_vader_ph_patch(sia)
    pos_th, neg_th = _get_label_thresholds()

    processed = _preprocess_for_vader(text) if patch_status.get("ph_patch_enabled") else (text or "")
    title, chunks = _split_long_text_chunks(processed)
    raw_text = (text or "").strip()

    if not raw_text:
        elapsed_ms = (time.time() - start) * 1000.0
        return 0.0, "neutral", elapsed_ms, {
            "library": "nltk-vader",
            "mode": "longform_weighted",
            "chunks_analyzed": 0,
            "title_present": False,
            "weights": {"title": 0.25, "lead": 0.35, "body": 0.40},
            "threshold_pos": pos_th,
            "threshold_neg": neg_th,
            **patch_status,
        }

    # Fallback for short content: standard VADER on full text.
    if len(raw_text) < 350:
        score = float(sia.polarity_scores(processed).get("compound", 0.0))
        label = _label_from_compound(score, pos_threshold=pos_th, neg_threshold=neg_th)
        elapsed_ms = (time.time() - start) * 1000.0
        return score, label, elapsed_ms, {
            "library": "nltk-vader",
            "mode": "short_text",
            "chunks_analyzed": 1,
            "title_present": bool(title),
            "weights": {"full_text": 1.0},
            "threshold_pos": pos_th,
            "threshold_neg": neg_th,
            **patch_status,
        }

    title_score = float(sia.polarity_scores(title).get("compound", 0.0)) if title else None
    chunk_scores = [float(sia.polarity_scores(c).get("compound", 0.0)) for c in chunks] if chunks else []

    if chunk_scores:
        lead_scores = chunk_scores[:2]
        body_scores = chunk_scores[2:] if len(chunk_scores) > 2 else chunk_scores
        lead_avg = sum(lead_scores) / len(lead_scores)
        body_avg = sum(body_scores) / len(body_scores)
    else:
        lead_avg = float(sia.polarity_scores(raw_text).get("compound", 0.0))
        body_avg = lead_avg

    w_title, w_lead, w_body = 0.25, 0.35, 0.40
    if title_score is None:
        # Rebalance when title is unavailable.
        w_title, w_lead, w_body = 0.0, 0.45, 0.55

    compound = (w_title * (title_score or 0.0)) + (w_lead * lead_avg) + (w_body * body_avg)
    label = _label_from_compound(compound, pos_threshold=pos_th, neg_threshold=neg_th)
    elapsed_ms = (time.time() - start) * 1000.0
    metadata = {
        "library": "nltk-vader",
        "mode": "longform_weighted",
        "chunks_analyzed": len(chunk_scores),
        "title_present": title_score is not None,
        "weights": {"title": w_title, "lead": w_lead, "body": w_body},
        "title_score": title_score,
        "lead_avg_score": lead_avg,
        "body_avg_score": body_avg,
        "threshold_pos": pos_th,
        "threshold_neg": neg_th,
        **patch_status,
    }
    return compound, label, elapsed_ms, metadata


def analyze_sentiment_vader(text: str) -> Tuple[float, str, float]:
    """
    Returns: (compound_score, label, elapsed_ms)
    compound_score in [-1, 1]
    label in {positive|neutral|negative}
    """
    compound, label, elapsed_ms, _ = analyze_sentiment_vader_detailed(text)
    return compound, label, elapsed_ms

def build_bias_row_for_vader(article_id: int, text: str) -> Dict[str, Any]:
    compound, label, elapsed_ms, details = analyze_sentiment_vader_detailed(text)
    return {
        "article_id": article_id,
        "model_version": "vader_v1",
        "model_type": "sentiment",
        "sentiment_score": compound,
        "sentiment_label": label,
        "confidence_score": None,
        "processing_time_ms": int(elapsed_ms),
        "model_metadata": details,
    }


def build_comprehensive_bias_analysis(article_id: int, text: str) -> list[Dict[str, Any]]:
    """
    Build sentiment analysis rows only.
    Political-bias generation is retired to reduce storage and noise.
    """
    return [build_bias_row_for_vader(article_id, text)]
