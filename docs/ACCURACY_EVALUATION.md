# Accuracy Evaluation (What to Say + What to Run)

This file is the stable doc path referenced by other docs.

If you see `docs/FINAL_ACCURACY_EVALUATION.md`, it contains the same content (kept for compatibility).

## Re-run exactly what `hybrid.tex` reports

Files referenced by the TeX draft:
- Taglish gold set JSON: `backend/app/ml/vader_ph_eval.v1.json`
- English gold set JSON: `backend/app/ml/distilbert_en_gold.v1.json`
- Manual benchmark CSV (n=200): `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

Scripts:
- Gold-set eval: `backend/scripts/evaluate_vader_ph_gold.py`
- Manual benchmark eval: `backend/scripts/evaluate_sentiment_benchmark.py`

## What I evaluated??

1) **Offline accuracy on a labeled gold set**
- Dataset: `backend/app/ml/vader_ph_eval.v1.json`
- Why: it’s **offline**, **repeatable**, and prints a clear report (accuracy + confusion matrix).

2) **Behavior check on real recent articles (optional, more “system” than “accuracy”)**
- Script: `backend/scripts/evaluate_vader_longform.py`
- Why: shows how the long-form sentiment scoring behaves on real news articles (distribution changes, examples).

## 1) Offline “gold set” accuracy (sentiment)

### What i should tell

- “We created a small labeled gold set of Taglish/PH news-style text with 3 classes: positive/neutral/negative.”
- “We ran the same gold set through multiple engines (VADER baseline, DistilBERT SST-2, and a hybrid router) and measured accuracy + confusion matrix.”
- “We tuned thresholds like the neutral band and routing threshold, and we keep the evaluation script in the repo so results are reproducible.”

### What you run?

From the repo root, start the ML container once:
- `docker compose up -d worker_ml`

Then run these inside the running container:

- VADER (patch on): `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model vader --ph-patch on`
- VADER (patch off): `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model vader --ph-patch off`
- DistilBERT: `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model distilbert`
- Hybrid: `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on`

### English-only gold set (DistilBERT baseline)

- `docker compose exec worker_ml env DISTILBERT_NEUTRAL_MIN_CONF=0 python /app/backend/scripts/evaluate_vader_ph_gold.py --model distilbert --file /app/backend/app/ml/distilbert_en_gold.v1.json --labels binary`

### If DistilBERT keeps re-downloading (use your old host cache)

If you already have models in `~/.cache/huggingface` on your original machine, you can mount that cache instead of the repo-local `./.cache/huggingface`:

- `docker compose -f docker-compose.yml -f docker-compose.hf-home-cache.yml up -d --force-recreate worker_ml`

(Tip: you can also keep a local-only `docker-compose.override.yml` that mounts `~/.cache/huggingface` so you don't have to pass extra `-f` flags. This repo gitignores that file.)

## 2) Manual benchmark (n=200 CSV “real-world” test)

- File: `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`
- Run: `docker compose exec worker_ml python /app/backend/scripts/evaluate_sentiment_benchmark.py --file /app/backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

Notes:
- This script evaluates `vader,distilbert,hybrid` by default, so the first run may download DistilBERT weights if they are not already present in the mounted HF cache.
- If you only want a quick demo without transformers downloading, run VADER only:
  - `docker compose exec worker_ml python /app/backend/scripts/evaluate_sentiment_benchmark.py --models vader --file /app/backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

If you want LaTeX tables printed (for thesis copy/paste), add `--latex on`.

## 3) Optional: evaluation on real articles (behavior check)

- `docker compose -f docker-compose.prod.yml run --rm worker_ml python /app/backend/scripts/evaluate_vader_longform.py --days 30 --limit 300 --ph-patch on --model hybrid`

