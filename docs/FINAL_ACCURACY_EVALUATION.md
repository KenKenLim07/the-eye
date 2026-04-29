# Accuracy Evaluation (What to Say + What to Run)

This project’s “accuracy” question is mainly about **sentiment classification** (positive / neutral / negative).

## Re-run exactly what `hybrid.tex` reports

Files referenced by the TeX draft:
- Taglish gold set JSON: `backend/app/ml/vader_ph_eval.v1.json`
- English gold set JSON: `backend/app/ml/distilbert_en_gold.v1.json`
- Manual benchmark CSV (n=200): `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

Scripts:
- Gold-set eval: `backend/scripts/evaluate_vader_ph_gold.py`
- Manual benchmark eval (prints LaTeX tables): `backend/scripts/evaluate_sentiment_benchmark.py`

## What I evaluated (defense-friendly)

1) **Offline accuracy on a labeled gold set (recommended to show the panel)**
- Dataset: `backend/app/ml/vader_ph_eval.v1.json`
- Why: it’s **offline**, **repeatable**, and prints a clear report (accuracy + confusion matrix).

2) **Behavior check on real recent articles (optional, more “system” than “accuracy”)**
- Script: `backend/scripts/evaluate_vader_longform.py`
- Why: shows how the long-form sentiment scoring behaves on real news articles (distribution changes, examples).

## 1) Offline “gold set” accuracy (sentiment)

### What you tell the teacher

- “We created a small labeled gold set of Taglish/PH news-style text with 3 classes: positive/neutral/negative.”
- “We ran the same gold set through multiple engines (VADER baseline, DistilBERT SST-2, and a hybrid router) and measured accuracy + confusion matrix.”
- “We tuned thresholds like the neutral band and routing threshold, and we keep the evaluation script in the repo so results are reproducible.”

### What you run (works great in Docker)

From the repo root, start the ML container once:

- `docker compose up -d worker_ml`

Then run these inside the running container (avoids creating a new one-off container and re-downloading weights):

**VADER baseline (with PH patch):**
- `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model vader --ph-patch on`

**VADER baseline (patch off) — for the “before vs after” table:**
- `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model vader --ph-patch off`

**DistilBERT:**
- `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model distilbert`

**Hybrid (router):**
- `docker compose exec worker_ml python /app/backend/scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on`

### English-only gold set (DistilBERT baseline)

To match the TeX baseline where DistilBERT is treated as strictly binary (SST-2 style), run it with neutralization disabled:
- `docker compose exec worker_ml env DISTILBERT_NEUTRAL_MIN_CONF=0 python /app/backend/scripts/evaluate_vader_ph_gold.py --model distilbert --file /app/backend/app/ml/distilbert_en_gold.v1.json --labels binary`

### If DistilBERT keeps re-downloading (use your old host cache)

If you already have models in `~/.cache/huggingface` on your original machine, you can mount that cache instead of the repo-local `./.cache/huggingface`:

- `docker compose -f docker-compose.yml -f docker-compose.hf-home-cache.yml up -d --force-recreate worker_ml`

(Tip: you can also keep a local-only `docker-compose.override.yml` that mounts `~/.cache/huggingface` so you don't have to pass extra `-f` flags. This repo gitignores that file.)

(Then rerun DistilBERT with the same `docker compose exec worker_ml ...` commands.)

## 2) Manual benchmark (n=200) + copy/paste LaTeX tables

This is what generates the TeX tables `tab:benchmark` and `tab:benchmark-binary`:
- `docker compose exec worker_ml python /app/backend/scripts/evaluate_sentiment_benchmark.py --file /app/backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

Notes:
- This script evaluates `vader,distilbert,hybrid` by default, so the first run may download DistilBERT weights if they are not already present in the mounted HF cache.
- If you only want a quick demo without transformers downloading, run VADER only:
  - `docker compose exec worker_ml python /app/backend/scripts/evaluate_sentiment_benchmark.py --models vader --file /app/backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

If you want LaTeX tables printed (for thesis copy/paste), add `--latex on`.

What the script prints (what you can point at):
- overall **Accuracy**
- class distribution (true vs predicted)
- **Confusion matrix** (true → predicted)
- some misclassified examples (so you can discuss limitations)

### How to improve credibility (simple)

- Add more items to `backend/app/ml/vader_ph_eval.v1.json` (keep labels balanced).
- Keep a screenshot of the terminal output (or paste results into your thesis methodology/results section).

## 3) Optional: evaluation on real articles (not “accuracy”, but good discussion)

This compares legacy single-pass VADER vs the newer long-form scoring on recent Supabase articles:
- `docker compose -f docker-compose.prod.yml run --rm worker_ml python /app/backend/scripts/evaluate_vader_longform.py --days 30 --limit 300 --ph-patch on --model hybrid`

Use this when the panel asks “does it work on real news text?” or “what changed vs baseline?”.

## Notes / limitations (say this if asked)

- “Gold set size is limited (manual labeling), so we report it as an estimate and show misclassifications.”
- “For NER/entities we mostly did qualitative validation (spot-checking extracted entities), because building a full labeled NER dataset was out of scope for the capstone timeline.”
