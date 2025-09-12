# ML/NLP Integration Guide

This document describes how we integrate free, CPU-friendly ML/NLP into the Philippine News Aggregator. It covers phases, database schema, backend tasks/endpoints, frontend surfaces, dependencies, and an operational rollout plan.

## Goals
- Sentiment and bias analysis per article with versioned results
- Trend aggregation and simple forecasts
- Assistive category quality (suggestions, not destructive)
- No paid APIs; CPU-only minimal stack

## Stack Overview
- Ingestion: Scrapers → FastAPI → Supabase (existing)
- ML: Celery tasks pull articles from Supabase → compute → write back
- API: FastAPI endpoints to trigger/fetch analysis and trends
- Frontend: Next.js surfaces sentiment/bias and trends

## Phases
1. Phase 1: Sentiment & Bias Detection (Minimal)
   - VADER (NLTK) → sentiment label + score
   - Optional (behind flag): Flair/HuggingFace bias classifier (left/right/neutral)
2. Phase 2: Trend Forecasting
   - Aggregates by source/category over time
   - Prophet or scikit-learn for simple forecasts
   - Topic clustering (TF‑IDF + KMeans/DBSCAN) to detect emerging themes
3. Phase 3: Advanced
   - spaCy NER to extract entities; join with trends/bias
   - HF fine-tuning (optional) for better bias detection
   - Deep embeddings for recommendations/similarity if needed

## Database Schema Additions

Create two new tables. Use these as a reference in Supabase SQL Editor.

```sql
-- Versioned per-article analysis
CREATE TABLE IF NOT EXISTS bias_analysis (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES articles(id) ON DELETE CASCADE,
    model_version TEXT NOT NULL,          -- e.g., 'vader_v1', 'flair_v1'
    model_type TEXT NOT NULL,             -- 'sentiment' | 'political_bias' | 'toxicity'

    sentiment_score FLOAT,
    sentiment_label TEXT,                 -- 'positive' | 'neutral' | 'negative'
    political_bias_score FLOAT,           -- -1..1 (optional)
    toxicity_score FLOAT,                 -- 0..1 (optional)

    confidence_score FLOAT,
    processing_time_ms INT,
    model_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(article_id, model_version, model_type)
);
CREATE INDEX IF NOT EXISTS idx_bias_article_id ON bias_analysis(article_id);
CREATE INDEX IF NOT EXISTS idx_bias_model_version ON bias_analysis(model_version);
CREATE INDEX IF NOT EXISTS idx_bias_created_at ON bias_analysis(created_at);

-- Predictions & aggregates
CREATE TABLE IF NOT EXISTS pattern_predictions (
    id SERIAL PRIMARY KEY,
    model_version TEXT NOT NULL,          -- 'sklearn_v1' | 'prophet_v1'
    model_type TEXT NOT NULL,             -- 'trend' | 'forecast' | 'cluster_summary'

    scope_type TEXT NOT NULL,             -- 'source' | 'category' | 'global'
    scope_value TEXT NOT NULL,            -- e.g., 'Philstar' | 'Business' | 'all'

    horizon TEXT NOT NULL,                -- '1d' | '7d' | '30d'
    predicted_value FLOAT,
    confidence_score FLOAT,
    model_metadata JSONB,

    created_at TIMESTAMP DEFAULT NOW(),
    valid_from TIMESTAMP DEFAULT NOW(),
    valid_until TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pred_model_version ON pattern_predictions(model_version);
CREATE INDEX IF NOT EXISTS idx_pred_scope ON pattern_predictions(scope_type, scope_value);
CREATE INDEX IF NOT EXISTS idx_pred_horizon ON pattern_predictions(horizon);
```

Optional view to avoid client-side aggregation loops:
```sql
CREATE OR REPLACE VIEW v_article_counts_weekly AS
SELECT DATE_TRUNC('week', published_at) AS week,
       source,
       category,
       COUNT(*) AS n
FROM articles
WHERE published_at IS NOT NULL
GROUP BY 1,2,3;
```

## Backend Changes

Directories to add:
- `backend/app/ml/bias.py` — VADER sentiment; optional Flair/HF classifiers
- `backend/app/ml/trends.py` — aggregates; optional forecasts/clusters
- `backend/app/workers/ml_tasks.py` — Celery tasks for analysis and nightly aggregates

Hooking point (already present and now normalized):
- `backend/app/pipeline/store.py` → after inserts (or in calling tasks), enqueue `analyze_articles_task` with inserted IDs.

Environment flags (`backend/app/core/config.py`):
- `ML_ENABLE=true` to toggle ML
- `ML_MODE=minimal|advanced` to pick VADER-only vs transformer extras

### Endpoints (FastAPI)
- `POST /ml/analyze`
  - Body: `{ article_ids?: number[], since?: ISODate, model_version?: string, force?: boolean }`
  - Behavior: queues `analyze_articles_task`
- `GET /articles/{id}/analysis`
  - Returns latest `bias_analysis` row for the article
- `GET /ml/trends?scope=source:Philstar&horizon=7d`
  - Returns aggregates/predictions (from `pattern_predictions` or on-the-fly)

### Celery Tasks
- `analyze_articles_task(article_ids: list[int])`
  - Fetch articles → compute sentiment/bias → insert into `bias_analysis`
- `nightly_ml_aggregates_task()`
  - Build aggregates and (optional) forecasts → insert into `pattern_predictions`

## Dependencies (free, CPU)
Add to `backend/requirements.txt`:
- Minimal: `nltk`, `scikit-learn`, `pandas`, `numpy`
- Optional: `flair` or `transformers`, `prophet` (can be added in Phase 2)

## Frontend Surfaces (Next.js)
- Article Row/Card: show sentiment badge (Positive/Neutral/Negative)
- Article Detail: “Bias & Sentiment” panel (latest analysis row)
- Trends page: counts and simple charts by source/category; sentiment average line

Fetching patterns:
- Extend `src/lib/articles.ts` with helper to fetch `/articles/{id}/analysis`
- For trends: call `/ml/trends` or query a Supabase view

## Versioning & Model Registry
- Every analysis row stores `model_version` and `model_type`
- Keep an in-code registry with description/params per version for reproducibility

## Operational Plan
1. Apply schema (tables + optional view)
2. Add minimal deps and implement VADER pipeline
3. Add Celery tasks + endpoints; wire enqueue after article inserts
4. Backfill: run analysis for recent N days (batch via POST `/ml/analyze`)
5. Add minimal UI surfaces (badge + detail panel)
6. Monitor performance & correctness; iterate

## Backfill Strategy
- Batch in chunks (e.g., 200–500 article IDs per enqueue)
- Limit concurrency to avoid Supabase rate limits
- Schedule nightly large backfills if needed

## Notes & Caveats
- Keep article data immutable; all ML writes go to separate tables
- Start with VADER (fast) and move transformers to nightly jobs if CPU-bound
- Continue using category normalization on write (already wired)

## Roadmap (Optional)
- Flair/HF sentiment & bias (improved accuracy)
- Topic modeling & auto-tags, entity extraction (spaCy)
- Forecasts with Prophet/ARIMA; cluster summaries per period
- Recommendations via embeddings (when needed)

---
If you need the exact SQL applied and code scaffolding for tasks/endpoints, see this doc’s companion commits and the `backend/app/ml/` and `backend/app/workers/` modules once added. 