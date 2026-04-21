# SYSTEM_FACTS (Verified)

This file is intended to be a **verified source of truth** for writing the hardbound thesis.

Rules:
- Only include facts that are verifiable in this repo (code/config/docs) or in the referenced LaTeX artifact `thesis latex/ACM_Hypertext_Conference_Template/hybrid.tex`.
- Prefer exact env var names, defaults, and script/file names.

Verified on:
- Date: 2026-04-17 (Asia/Manila)
- Git commit: `6ec0ce4ff8bf5a4d8f7c54937762e9d2784232af`

## Project identity
- System name used in ACM paper: **PH VibeCheck AI** (`thesis latex/ACM_Hypertext_Conference_Template/hybrid.tex`).
- Repo: `the-eye` (this workspace).

## Data sources (scrapers)
Implemented scraper modules in `backend/app/scrapers/`:
- `abs_cbn.py`, `gma.py`, `inquirer.py`, `manila_bulletin.py`, `manila_times.py`, `philstar.py`, `rappler.py`, `sunstar.py`

## Scheduled ingestion (Celery beat)
`backend/app/workers/celery_app.py` defines `celery.conf.beat_schedule`:
- Rappler: every 1.00 hours
- GMA: every 1.08 hours
- Philstar: every 1.17 hours
- Inquirer: every 1.25 hours
- Manila Bulletin: every 1.33 hours
- Manila Times: every 1.42 hours
- Sunstar: every 1.50 hours
- ABS-CBN: every 2.00 hours, enabled by default when `ENABLE_ABS_CBN_SCRAPER=1` (default is `"1"`).

Queues and routing in `backend/app/workers/celery_app.py`:
- Scrape tasks go to `scrape` (or `scrape_headed` for ABS-CBN if `ABS_CBN_FORCE_HEADED=1`)
- ML tasks go to `ml`

## Sentiment pipeline output (Supabase tables)
From `backend/app/workers/ml_tasks.py`:
- Writes sentiment rows into `bias_analysis` via upsert with `on_conflict="article_id,model_version,model_type"`.
- Also upserts a public cache into `article_sentiment_public` with `on_conflict="article_id"`.
- `build_comprehensive_bias_analysis()` in `backend/app/ml/bias.py` currently returns **sentiment rows only** (political bias generation is retired).

## “Active” sentiment model version (avoids duplicates)
From `backend/app/ml/bias.py`:
- Env selects mode: `SENTIMENT_MODEL` in `{vader, distilbert, hybrid}`; default is `"hybrid"`.
- Model version key:
  - If `SENTIMENT_MODEL_VERSION` is set, it is used as-is.
  - Else defaults:
    - `vader` → `vader_v1`
    - `distilbert` → `sentiment_distilbert_v1`
    - `hybrid` → `sentiment_hybrid_v1`

## Hybrid sentiment router (VADER + DistilBERT)
Implemented in `backend/app/ml/bias.py` as `analyze_sentiment_hybrid_detailed(text)`:
- Computes a Tagalog-signal ratio via `_tagalog_signal(text)`:
  - Tokenization: `re.findall(r"[a-zñ]+", raw)` (punctuation/emoji/etc. are ignored for the signal).
  - Hits: token is in `_TAGALOG_FUNCTION_WORDS` OR `_TAGALOG_SIGNAL_TOKENS`.
  - Ratio = hits / tokens.
- Routing:
  - `TAGALOG_SIGNAL_THRESHOLD` default = `0.06`; clamp to `[0,1]`.
  - If ratio ≥ threshold → route `"vader"`, else route `"distilbert"`.
  - Special case: if routed to DistilBERT and the text looks like a neutral reporting preface (e.g. “According to …”), route is forced to `"vader"` with `route_reason="reporting_preface"`.
- Failovers:
  - If VADER throws (e.g., offline lexicon issue), hybrid returns `route="distilbert_fallback"` and uses DistilBERT.
  - If DistilBERT returns metadata with `error`, hybrid falls back to VADER with `route="vader_fallback"`.

Hybrid metadata keys written into `model_metadata` (example fields):
- `library: "hybrid"`, `engine: "vader_or_distilbert"`, `route`, `route_reason`
- `tagalog_signal_threshold`, `tagalog_signal_ratio`, `tagalog_signal_hits`, `tagalog_signal_tokens`
- `route_metadata` = the underlying model’s detailed metadata

## VADER long-form scoring (news-tuned)
Implemented in `backend/app/ml/bias.py` as `analyze_sentiment_vader_detailed(text)`:
- Preprocess (only when PH patch enabled): `_preprocess_for_vader(text)` applies:
  - Phrase substitutions from `vader_ph_lexicon.v1.json` (regex with conservative boundaries)
  - Optional Tagalog contrast-word normalization to English `"but"` (see “PH patch” below)
- Chunking:
  - If input contains `\n\n`, first block is treated as title; remainder as body.
  - Body is split into sentences and chunked to `max_chunk_chars=700`.
- Short text fallback:
  - If raw text length `< 350`, uses single-pass VADER on full text.
- Weighted aggregation for long text:
  - Default weights: `title=0.25`, `lead=0.35` (first 2 chunks), `body=0.40`.
  - If title missing: weights rebalance to `lead=0.45`, `body=0.55`.
- Label thresholds:
  - Default band is `pos>=0.05`, `neg<=-0.05`.
  - Can widen via `VADER_NEUTRAL_BAND` (e.g. `0.16` means pos≥0.16 and neg≤-0.16).

## VADER initialization (offline-friendly)
Implemented in `backend/app/ml/bias.py` `_ensure_vader()`:
- Tries `nltk.sentiment.SentimentIntensityAnalyzer()`.
- If NLTK lexicon missing (`LookupError`), tries `vaderSentiment.vaderSentiment.SentimentIntensityAnalyzer` (bundled lexicon).
- If that fails, attempts `nltk.download("vader_lexicon")` and retries.
- Any success path then applies the PH patch (if enabled).

## PH lexicon patch (Tagalog/Taglish)
Patch file: `backend/app/ml/vader_ph_lexicon.v1.json`
- `version`: `ph_taglish_v1`
- Counts (as of this repo state):
  - `lexicon` terms: 248
  - `negations`: 4
  - `boosters`: 6
  - `phrases`: 53
  - `but_words`: 3
- Applied in `backend/app/ml/bias.py` `_apply_vader_ph_patch(sia)`:
  - Controlled by env `VADER_PH_PATCH` (truthy enables).
  - Applies **once per process** (module-level flag).
  - Updates `sia.lexicon` with:
    - `lexicon` entries
    - plus phrase tokens (each phrase maps to a single token with a valence)
  - Collision handling:
    - If a token already exists in base VADER and is NOT allowlisted for override, it is skipped (counted in `ph_lexicon_skipped_existing`).
    - Allowlist is `override_existing_allowlist` in the JSON (currently empty in this repo).
  - Optional constant tweaks when available:
    - Adds `negations` into `constants.NEGATE`
    - Adds boosters into `constants.BOOSTER_DICT`
    - Adds Tagalog “but equivalents” into `constants.BUT_WORDS` when enabled
      - Can disable BUT_WORDS injection via `VADER_TL_BUT_WORDS=0` (default is enabled when env is unset)

Contrast normalization in preprocessing (`backend/app/ml/bias.py` `_preprocess_for_vader`):
- If env `VADER_TL_BUT_NORMALIZE` is unset → normalization is **enabled** by default.
- Setting `VADER_TL_BUT_NORMALIZE=0` disables replacing Tagalog contrast words with `"but"`.

## DistilBERT transformer path (CPU)
Implemented in `backend/app/ml/sentiment_transformer.py` as `analyze_sentiment_distilbert_detailed(text)`:
- Default model id: `distilbert-base-uncased-finetuned-sst-2-english` (SST-2)
- Truncation / bounds:
  - Raw input clipped to `DISTILBERT_MAX_CHARS` (default 2000 chars)
  - Transformer token truncation uses `max_length=DISTILBERT_MAX_LENGTH` (default 512 tokens)
- Confidence to neutral:
  - `DISTILBERT_NEUTRAL_MIN_CONF` default `0.60`
  - If model confidence `< neutral_min_conf`, output label becomes `neutral` and compound score becomes `0.0`
- Score mapping:
  - Transformer returns `{label: POSITIVE|NEGATIVE, score: [0,1]}`
  - Compound in `[-1,1]` is `+score` for POSITIVE and `-score` for NEGATIVE.
- Reporting-preface neutralization (binary SST-2 mitigation):
  - Function `_should_neutralize_reporting(text)` short-circuits to neutral when:
    - text matches a reporting prefix (e.g., “According to…”, “Confirmed…”, “As of…”)
    - and the remaining tokens contain no strong sentiment hints
  - Enabled by default when `DISTILBERT_NEUTRALIZE_REPORTING` is **unset**.
  - If `DISTILBERT_NEUTRALIZE_REPORTING` is set and falsey, neutralization is disabled.

DistilBERT caching / offline behavior (`backend/app/ml/sentiment_transformer.py` `_get_pipeline()`):
- Uses env:
  - `HF_HOME` as cache root (code tries `HF_HOME` and `HF_HOME/hub`)
  - `HF_HUB_OFFLINE` or `TRANSFORMERS_OFFLINE` → forces `local_files_only=True`
- Network-hardening defaults are set in-process:
  - `HF_HUB_ETAG_TIMEOUT=60`
  - `HF_HUB_DOWNLOAD_TIMEOUT=300`
  - `HF_HUB_DISABLE_TELEMETRY=1`

## Compose defaults used in this repo (worker_ml)
From `docker-compose.yml` `worker_ml` environment:
- `VADER_PH_PATCH=1`
- `SENTIMENT_MODEL=hybrid`
- `SENTIMENT_MODEL_VERSION=sentiment_hybrid_v1`
- `DISTILBERT_MODEL_ID=distilbert-base-uncased-finetuned-sst-2-english`
- `TAGALOG_SIGNAL_THRESHOLD=0.15`
- `VADER_NEUTRAL_BAND=0.16`
- `HF_HOME=/root/.cache/huggingface`
Volume mount (host → container) for HF cache:
- `${HOME}/.cache/huggingface:/root/.cache/huggingface`

## Evaluation scripts (thesis-defensible benchmarking)
Gold set:
- File: `backend/app/ml/vader_ph_eval.v1.json`
  - `version`: `ph_taglish_eval_v1`
  - `items`: 130 labeled examples (`positive|neutral|negative`)
- Runner: `backend/scripts/evaluate_vader_ph_gold.py`
  - `--model {vader,distilbert,hybrid}`
  - `--ph-patch {auto,on,off}`
  - Can override thresholds for experiments:
    - `--vader-neutral-band` sets `VADER_NEUTRAL_BAND`
    - `--tagalog-signal-threshold` sets `TAGALOG_SIGNAL_THRESHOLD`
    - `--distilbert-neutral-min-conf` sets `DISTILBERT_NEUTRAL_MIN_CONF`

Real-news drift comparison:
- Runner: `backend/scripts/evaluate_vader_longform.py`
  - Samples recent real articles from Supabase `articles` table.
  - Compares legacy single-pass VADER vs the selected “new path” model (`--model`).

Labeling protocol and benchmark sample:
- `docs/sentiment_benchmark_labeling.md`
- `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv` (example sample file present in repo)

## Backfill / rescore scripts
Rescore sentiment rows (enqueue ML tasks):
- `scripts/backfill_ml_analysis.py`
  - `--days N` lookback window
  - `--force` rescoring mode: re-enqueue ALL articles in window (upsert overwrites existing sentiment rows for the active model version)

Refresh public cache table:
- `scripts/backfill_article_sentiment_public.py`
  - Pulls latest sentiment rows from `bias_analysis` and upserts into `article_sentiment_public`

## Special characters and whitespace (what we do / don’t do)
- We do **not** globally strip punctuation or normalize whitespace before ML.
- VADER path:
  - Uses limited deterministic phrase/contrast substitutions (regex-based) when PH patch is enabled.
  - Otherwise passes text to the VADER analyzer (which internally tokenizes and uses punctuation cues).
- DistilBERT path:
  - Passes the clipped raw text to the Hugging Face tokenizer (punctuation/quotes/dashes are handled by the tokenizer).
- Hybrid tagalog-signal:
  - Uses regex tokenization `[a-zñ]+`, so punctuation is ignored for routing signals.
