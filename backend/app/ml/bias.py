import time
from typing import Tuple, Dict, Any
import json
import os

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


# ----------------------------------------------------------------------------
# Externalized Philippine political keywords
# ----------------------------------------------------------------------------
_POLITICAL_CFG_CACHE: Dict[str, Any] = {}


def _load_political_keywords() -> Dict[str, Any]:
	"""Load political keyword config from JSON; fallback to embedded defaults."""
	global _POLITICAL_CFG_CACHE
	if _POLITICAL_CFG_CACHE:
		return _POLITICAL_CFG_CACHE
	cfg_path = os.path.join(os.path.dirname(__file__), 'keywords_ph.json')
	defaults = {
		"version": "embedded",
		"keywords": {},
		"weights": {}
	}
	try:
		with open(cfg_path, 'r', encoding='utf-8') as f:
			cfg = json.load(f)
			_POLITICAL_CFG_CACHE = cfg or defaults
			return _POLITICAL_CFG_CACHE
	except Exception:
		_POLITICAL_CFG_CACHE = defaults
		return _POLITICAL_CFG_CACHE


def get_political_keywords_and_weights() -> Tuple[Dict[str, Any], Dict[str, float], str]:
	cfg = _load_political_keywords()
	keywords = cfg.get('keywords') or {}
	weights = cfg.get('weights') or {}
	version = cfg.get('version') or 'embedded'
	return keywords, weights, version


# Existing sentiment analysis

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


# ============================================================================
# PHILIPPINE POLITICAL BIAS ANALYSIS SYSTEM
# ============================================================================

# Fallback embedded keyword sets (will be overridden if JSON is present)
POLITICAL_KEYWORDS = {
	# Pro-Government Keywords
	"pro_gov_current_admin": [
		"marcos", "bbm", "bongbong marcos", "sara duterte", "administration",
		"government success", "progress", "development", "infrastructure"
	],
	"pro_gov_administration": [
		"president", "administration", "cabinet", "executive", "leadership",
		"government", "official", "policy", "program", "initiative"
	],
	"pro_gov_policies": [
		"build build build", "infrastructure", "economic growth", "job creation",
		"poverty reduction", "healthcare reform", "education reform"
	],
	"pro_gov_positive_terms": [
		"successful", "effective", "efficient", "progress", "achievement",
		"improvement", "beneficial", "positive", "good governance"
	],
	# Opposition Keywords
	"pro_opp_opposition_figures": [
		"leni robredo", "opposition", "liberal party", "critics", "activists",
		"human rights groups", "civil society"
	],
	"pro_opp_criticism": [
		"corruption", "incompetence", "failure", "scandal", "controversy",
		"investigation", "accountability", "transparency"
	],
	"pro_opp_protest": [
		"protest", "rally", "demonstration", "activism", "dissent",
		"opposition", "criticism", "resistance"
	],
	"pro_opp_negative_terms": [
		"failed", "corrupt", "ineffective", "problematic", "controversial",
		"criticized", "questioned", "disputed"
	],
	# Neutral Keywords
	"neutral_general": [
		"philippines", "filipino", "manila", "cebu", "davao", "news",
		"report", "statement", "announcement", "conference"
	],
	"neutral_process": [
		"congress", "senate", "house", "legislation", "bill", "law",
		"committee", "hearing", "session", "vote"
	],
	"neutral_institutional": [
		"supreme court", "comelec", "doj", "dilg", "dof", "doh",
		"deped", "dti", "da", "denr"
	]
}


def analyze_political_bias_philippine(text: str) -> Tuple[float, str, float, Dict[str, Any]]:
	"""
	Analyze political bias in Philippine news articles.
	Returns: (bias_score, direction, elapsed_ms, metadata)
	"""
	start = time.time()
	text_lower = (text or "").lower()

	# Prefer external keywords/weights when available
	kw_cfg, weights, version = get_political_keywords_and_weights()
	keywords = kw_cfg if kw_cfg else POLITICAL_KEYWORDS

	# Count keyword matches
	keyword_matches = {}
	total_matches = 0
	for category, terms in keywords.items():
		count = 0
		# Match multi-word terms first
		sorted_terms = sorted(terms, key=len, reverse=True)
		for term in sorted_terms:
			term_l = term.lower().strip()
			if not term_l:
				continue
			if ' ' in term_l:
				count += 1 if term_l in text_lower else 0
			else:
				# word-boundary match for single words
				import re as _re
				if _re.search(rf"\b{_re.escape(term_l)}\b", text_lower):
					count += 1
		keyword_matches[category] = count
		total_matches += count

	# Compute component scores using configured weights when present
	w = lambda k, d: float(weights.get(k, d))
	pro_gov_score = (
		keyword_matches.get("pro_gov_current_admin", 0) * w("pro_gov_current_admin", 0.4) +
		keyword_matches.get("pro_gov_administration", 0) * w("pro_gov_administration", 0.3) +
		keyword_matches.get("pro_gov_policies", 0) * w("pro_gov_policies", 0.2) +
		keyword_matches.get("pro_gov_positive_terms", 0) * w("pro_gov_positive_terms", 0.1)
	)
	pro_opp_score = (
		keyword_matches.get("pro_opp_opposition_figures", 0) * w("pro_opp_opposition_figures", 0.3) +
		keyword_matches.get("pro_opp_criticism", 0) * w("pro_opp_criticism", 0.3) +
		keyword_matches.get("pro_opp_protest", 0) * w("pro_opp_protest", 0.2) +
		keyword_matches.get("pro_opp_negative_terms", 0) * w("pro_opp_negative_terms", 0.2)
	)
	neutral_score = (
		keyword_matches.get("neutral_general", 0) * w("neutral_general", 0.4) +
		keyword_matches.get("neutral_process", 0) * w("neutral_process", 0.3) +
		keyword_matches.get("neutral_institutional", 0) * w("neutral_institutional", 0.3)
	)

	# Calculate keyword-based score (0-1)
	if total_matches == 0:
		keyword_score = 0.0
	else:
		keyword_score = max(pro_gov_score, pro_opp_score) / max(total_matches, 1)

	# Source pattern analysis (simplified)
	source_pattern = 0.1 if any(word in text_lower for word in ["government", "official"]) else 0.0

	# Language patterns (simplified sentiment context)
	compound, _, _ = analyze_sentiment_vader(text)
	sentiment_context = abs(compound) if abs(compound) > 0.3 else 0.0

	formal_indicators = ["according to", "stated", "announced", "reported", "confirmed"]
	informal_indicators = ["slammed", "blasted", "hit back", "fired back"]
	formal_count = sum(1 for indicator in formal_indicators if indicator in text_lower)
	informal_count = sum(1 for indicator in informal_indicators if indicator in text_lower)
	if informal_count > formal_count:
		language_patterns = 0.2
	elif formal_count > informal_count:
		language_patterns = -0.1
	else:
		language_patterns = 0.0

	analysis_components = {
		"keyword_score": keyword_score,
		"source_pattern": source_pattern,
		"language_patterns": language_patterns,
		"sentiment_context": sentiment_context,
		"version": version
	}
	bias_score = (
		keyword_score * 0.6 +
		source_pattern * 0.1 +
		abs(language_patterns) * 0.1 +
		sentiment_context * 0.2
	)
	if pro_gov_score > pro_opp_score and bias_score > 0.1:
		direction = "pro_government"
	elif pro_opp_score > pro_gov_score and bias_score > 0.1:
		direction = "pro_opposition"
	else:
		direction = "neutral"
	confidence_score = min(1.0, bias_score + (total_matches / 20.0))
	elapsed_ms = (time.time() - start) * 1000.0
	metadata = {
		"direction": direction,
		"keyword_matches": keyword_matches,
		"processing_time_ms": int(elapsed_ms),
		"analysis_components": analysis_components
	}
	return bias_score, direction, elapsed_ms, metadata


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


def build_bias_row_for_philippine_political(article_id: int, text: str) -> Dict[str, Any]:
	"""Build a bias analysis row for Philippine political bias analysis."""
	bias_score, direction, elapsed_ms, metadata = analyze_political_bias_philippine(text)
	# Calculate confidence based on keyword matches and analysis strength
	total_keywords = sum(metadata["keyword_matches"].values())
	confidence_score = min(1.0, bias_score + (total_keywords / 10.0))
	return {
		"article_id": article_id,
		"model_version": "philippine_bias_v1",
		"model_type": "political_bias",
		"sentiment_score": None,
		"sentiment_label": None,
		"political_bias_score": bias_score,
		"toxicity_score": None,
		"confidence_score": confidence_score,
		"processing_time_ms": int(elapsed_ms),
		"model_metadata": metadata,
	}


def build_comprehensive_bias_analysis(article_id: int, text: str) -> list[Dict[str, Any]]:
	"""
	Build both VADER sentiment and Philippine political bias analysis.
	Returns a list of bias analysis rows.
	"""
	rows = []
	rows.append(build_bias_row_for_vader(article_id, text))
	rows.append(build_bias_row_for_philippine_political(article_id, text))
	return rows
