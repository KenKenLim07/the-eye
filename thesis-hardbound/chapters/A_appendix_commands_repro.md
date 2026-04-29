# Appendix A — Reproducibility and Run Commands

This appendix lists practical commands used to run, evaluate, and backfill PH VibeCheck AI in the Dockerized development environment. Paths are written relative to the repository root.

Prerequisites and initial setup (clone + required `.env` files) are documented in:
- `thesis-hardbound/chapters/F_appendix_user_guide.md`

## Start the stack

```bash
# Start core services (adjust if you run additional compose variants)
docker compose up -d redis api worker worker_ml beat

# Follow logs
docker compose logs -f worker_ml
docker compose logs -f beat
```

## Run a scraper manually (API-triggered)

The backend exposes an API route to trigger scraping per source. Example (GMA):

```bash
curl -sS -X POST "http://localhost:8000/scrape/run" \
  -H "Content-Type: application/json" \
  -d '{"source":"gma"}'
```

Supported sources include: `abs_cbn`, `gma`, `inquirer`, `manila_bulletin`, `manila_times`, `philstar`, `rappler`, `sunstar`.

Note: ABS-CBN scheduled scraping is controlled by `ENABLE_ABS_CBN_SCRAPER` (enabled by default in this repo). If you do not see ABS-CBN logs during scheduled runs, verify this env var is set in the running `beat` container environment.

## Export the manual benchmark sample (real news CSV)

Run inside the backend container (or locally if your environment has the backend dependencies and Supabase credentials configured):

```bash
docker compose exec worker_ml sh -lc "\
  cd /app/backend && \
  python scripts/export_sentiment_benchmark_sample.py \
    --start-local 2026-03-25 --end-local 2026-03-31 \
    --n 200 --min-per-source 20 --seed 42 \
"
```

Output (example, already present in this repo):
- `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`

## Evaluate the manual benchmark (writes JSON report)

After labeling `benchmark_sample_...csv` (two annotators + adjudication), run:

```bash
docker compose exec -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 worker_ml \
  sh -lc "\
    cd /app/backend && \
    python scripts/evaluate_sentiment_benchmark.py \
      --file reports/benchmark_sample_2026-03-25_2026-03-31.csv \
      --clean-text on \
      --exclude-noisy on \
      --models vader,distilbert,hybrid \
      --ph-patch on \
      --out reports/sentiment_benchmark_2026-03-25_2026-03-31.json \
  "
```

This produces the thesis-report JSON used in Chapter 5:
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.json`

## Evaluate sentiment (gold set)

Run inside the ML worker container:

```bash
# Hybrid (VADER+PH patch + DistilBERT SST-2)
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on"

# VADER only (with PH patch)
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_ph_gold.py --model vader --ph-patch on"

# DistilBERT only
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_ph_gold.py --model distilbert"
```

Optional parameter overrides for experiments:

```bash
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on --vader-neutral-band 0.16 --tagalog-signal-threshold 0.15 --distilbert-neutral-min-conf 0.60"
```

## Evaluate drift on real news (sample from Supabase)

```bash
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_longform.py --days 7 --limit 300 --model hybrid --ph-patch on"
```

## Offline mode for Hugging Face model loading

If the DistilBERT model weights are already cached in the worker’s HF cache directory, you can force offline mode:

```bash
docker compose exec -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 worker_ml \
  sh -lc "cd /app/backend && python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on"
```

Host-side cache preparation (recommended before long builds/downloads):

```bash
mkdir -p ~/.cache/huggingface
```

Windows (PowerShell) equivalent:

```powershell
# Create the Hugging Face cache directory under your user profile
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\\.cache\\huggingface" | Out-Null
```

## Backfill / rescore sentiment (Celery enqueue)

Rescore the last 7 days (force mode re-analyzes all articles in-window and overwrites via upsert using the active model version):

```bash
docker compose exec worker_ml python /app/scripts/backfill_ml_analysis.py --days 7 --batch-size 200 --force
```

## Refresh the public sentiment cache

If `bias_analysis` has sentiment rows but `article_sentiment_public` is missing or stale:

```bash
docker compose exec worker_ml python /app/scripts/backfill_article_sentiment_public.py --days 7 --dry-run
docker compose exec worker_ml python /app/scripts/backfill_article_sentiment_public.py --days 7 --apply --batch-size 200
```

## Check the hardbound thesis build

```bash
./thesis-hardbound/scripts/build_docx.sh
```

## (Optional) Write dashboard snapshot tables into Supabase

If you use the “snapshot tables” approach for demos (frontend reads precomputed snapshots), run:

```bash
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/trends_snapshot.py 7d --no-include-today"
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/correlation_snapshot.py 7d --no-include-today"
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/entity_rankings_snapshot.py 7d"
```

Note: these snapshot scripts require `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to be available in the container environment.
