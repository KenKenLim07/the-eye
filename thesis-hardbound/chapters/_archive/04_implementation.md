# Implementation

This chapter describes the concrete implementation of PH VibeCheck AI, with emphasis on the backend pipeline and the hybrid sentiment engine introduced in the updated system.

## Backend Stack and Deployment

The backend is implemented as a Dockerized FastAPI service [@fastapi; @docker] with asynchronous background processing handled by Celery [@celery] and Redis [@redis]. Persistent storage uses Supabase (PostgreSQL) [@supabase; @postgresql]. The frontend is implemented in Next.js and deployed on Vercel [@nextjs; @vercel].

At runtime, the system is split into responsibilities:
- **API service:** request handling and analytics endpoints.
- **Scrape workers:** scheduled scraping tasks per source.
- **ML workers:** sentiment inference and writing results to the analysis tables.

## Data Ingestion: News Scrapers

Eight sources are implemented as separate scraper modules in `backend/app/scrapers/`:
ABS-CBN, GMA, Inquirer, Manila Bulletin, Manila Times, Philstar, Rappler, and Sunstar. Scrapers normalize each discovered article into a consistent schema (URL, title, content, source metadata, and timestamps) before storing it in the `articles` table.

Scraping is scheduled via Celery Beat. In the current configuration, each source is assigned a periodic schedule tuned to its typical update frequency. ABS-CBN is enabled by default and can be routed to a headed scraping queue when required by CDN/Akamai behavior (see `thesis-hardbound/SYSTEM_FACTS.md`).

## ML Processing: One Sentiment Row per Article (Operational Design)

To keep analytics stable, the pipeline writes a single “active” sentiment row per article keyed by:
`(article_id, model_version, model_type='sentiment')`.

Sentiment outputs are upserted into:
- `bias_analysis` (internal, detailed; typically protected by RLS), and
- `article_sentiment_public` (public cache used by the frontend for coverage and lightweight listings).

The “active” model is selected by an environment variable:
- `SENTIMENT_MODEL ∈ {vader, distilbert, hybrid}` (default: `hybrid`).
- `SENTIMENT_MODEL_VERSION` (e.g., `sentiment_hybrid_v1`) pins which outputs are considered “current” for analytics and prevents duplication from multiple experimental runs.

## Hybrid Sentiment Engine (Taglish VADER + DistilBERT SST-2)

PH VibeCheck AI uses a hybrid sentiment engine that combines:
- **VADER**: lexicon-based sentiment with rule-based heuristics [@hutto2014vader], extended with a Philippine Tagalog/Taglish lexicon patch, and
- **DistilBERT**: a lightweight transformer classifier [@sanh2019distilbert; @devlin2018bert] fine-tuned on SST-2 [@socher2013sst] via Hugging Face Transformers [@huggingface_transformers].

The motivation for a hybrid design is domain reality: Philippine news text is frequently multilingual and code-switched (“Taglish”), and the model that performs best depends on the language mixture and the writing style of the snippet.

### VADER (News-Tuned Long-Form Weighting)

VADER is designed for short social text and can dilute polarity on long documents. To make it more suitable for articles, the implementation uses a long-form weighted strategy:
1. Split input into title and body (when the caller provides a title/body separator such as `\n\n`).
2. Segment the body into sentence-based chunks (bounded length).
3. Compute compound sentiment for:
   - title,
   - lead chunks (early body segments), and
   - remaining body chunks,
4. Aggregate with fixed weights (title, lead, body) to reduce dilution.

The resulting compound score remains in $[-1,1]$ and is converted into categorical labels using a configurable neutral band around zero (see “Label Threshold Tuning” below).

### Philippine Tagalog/Taglish VADER Patch

The PH patch extends the base VADER lexicon and constants using a JSON “source of truth” file:
`backend/app/ml/vader_ph_lexicon.v1.json`.

The patch includes:
- Tagalog/Taglish sentiment terms with valence scores,
- conservative Tagalog negations (e.g., “hindi”, “wala”, “huwag”),
- a small set of boosters/dampeners (e.g., “sobrang”, “medyo”),
- multi-word expressions (phrases) mapped into single tokens (e.g., “sana all” → `sana_all`) so they can be scored deterministically.

Patch application is **process-safe** (applied once per worker process) and is controlled by `VADER_PH_PATCH=1`. The system records patch status (version, counts, enabled/applied) in `model_metadata` for transparency and debugging.

### DistilBERT Sentiment (CPU, Truncated)

The transformer path uses `distilbert-base-uncased-finetuned-sst-2-english` (SST-2). Since transformer inference cost grows with sequence length, the implementation enforces two bounds:
- **Character clip:** input text is clipped to `DISTILBERT_MAX_CHARS` (default 2000).
- **Token truncation:** inference uses `max_length=DISTILBERT_MAX_LENGTH` (default 512 tokens) with truncation enabled.

Transformer outputs are mapped into a signed compound score:
- POSITIVE → `+score`, NEGATIVE → `-score`, with `score ∈ [0,1]`.

Because SST-2 is binary, a confidence-based neutral rule is applied:
- If confidence `< DISTILBERT_NEUTRAL_MIN_CONF` (default 0.60), the label is set to `neutral` and the compound score is set to `0.0`.

To mitigate over-polarization of purely factual reporting prefaces (e.g., “According to…”, “Confirmed…”), the implementation can neutralize such lines when they contain no strong sentiment hints.

### Hybrid Router: Language-Signal Heuristic + Failover

The hybrid router selects VADER vs DistilBERT per input using a lightweight Tagalog-signal ratio:
- Tokenization for the signal uses a conservative regex (`[a-zñ]+`), so punctuation/quotes/dashes do not affect the ratio.
- A token “hits” if it is a common Tagalog function word (e.g., “ang”, “ng”, “mga”, “pero”) or a conservative PH news/sentiment token (e.g., “patay”, “binaril”, “bagyo”, “krisis”).

If `tagalog_signal_ratio ≥ TAGALOG_SIGNAL_THRESHOLD`, route to the Taglish VADER path; otherwise route to DistilBERT. Additional router logic forces “reporting preface” text through the VADER path to avoid SST-2 artifacts on neutral reporting language.

The router is designed to be operationally robust:
- If VADER cannot initialize in an offline worker environment, it falls back to DistilBERT.
- If DistilBERT fails (e.g., missing cached files in offline mode), it falls back to VADER.

Routing decisions and detailed sub-model metadata are persisted in `model_metadata` for each sentiment row, enabling auditing and thesis-defensible interpretation.

## Label Threshold Tuning (Neutral Band)

VADER’s default decision thresholds are a small neutral band around zero (typically ±0.05). In news text, many sentences are factual and “weakly opinionated,” and a wider neutral band can reduce false positive/negative labeling on borderline lines.

The implementation supports tuning via:
- `VADER_NEUTRAL_BAND` (e.g., `0.16` means positive if ≥ 0.16 and negative if ≤ −0.16).

This tuning is intended as a defensible parameter study rather than an ad hoc adjustment: changes are evaluated on the gold set and on real-news drift comparisons (see Evaluation chapter).
