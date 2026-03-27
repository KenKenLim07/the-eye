# PH Eye

PH Eye is a full-stack capstone project that continuously collects Philippine online news, runs lightweight NLP (sentiment + NER), and renders dashboards for trends, correlation, entities, and per-source browsing.

## Features

- Automated scraping via Playwright-based scrapers (Celery workers).
- FastAPI backend with REST endpoints for articles and analytics.
- Sentiment analysis using NLTK VADER (stored in `bias_analysis` as `model_type='sentiment'`).
- Named Entity Recognition (spaCy) for PERSON/ORG/GPE extraction and aggregation.
- Frontend dashboards:
  - Home: latest articles grouped by source.
  - Trends: daily sentiment distribution and averages.
  - Correlation: Pearson correlation heatmap across sources using daily average sentiment.
  - Entities: top entities by mentions, optionally with average sentiment.
  - Source page: paginated listing with keyword search.

## Tech Stack

- Frontend: Next.js (App Router) + React + TypeScript + Tailwind CSS + Recharts + TanStack Query + Supabase JS.
- Backend: FastAPI + Celery + Redis + Playwright + BeautifulSoup4/lxml + Supabase (PostgreSQL).
- NLP: NLTK VADER, spaCy.
- Infra: Docker Compose (Redis + API + worker + beat).

## Architecture

```mermaid
flowchart LR
  Sources[Philippine News Sites] -->|Playwright Scrapers| Worker[Celery Worker]
  Beat[Celery Beat Scheduler] --> Worker
  Worker -->|write| DB[(Supabase Postgres)]

  API[FastAPI REST API] -->|read/write| DB
  Worker -->|queue| Redis[(Redis)]
  API --> Redis

  UI[Next.js Frontend] -->|fetch| API
  UI -->|read| DB
```

Notes:
- The frontend reads most aggregates from the backend (`NEXT_PUBLIC_BACKEND_URL`), and also reads article rows directly from Supabase in some views.
- Correlation is computed from daily average sentiment scores (Pearson `r`) across overlapping days per source pair.

## Repo Structure (Relevant)

- `src/`: Next.js frontend (pages in `src/app/*`).
- `src/types/database.ts`: Supabase-generated DB types (see below).
- `backend/app/`: FastAPI application (`backend/app/main.py` is the entrypoint).
- `backend/app/workers/`: Celery worker + tasks.
- `backend/app/scrapers/`: Source scrapers.
- `backend/app/scrapers/support/`: Shared scraper helpers (stealth profile + Playwright/http wrappers).
- `backend/scripts/`: maintenance and analysis scripts.
- `docker-compose.yml`: Redis + api + worker + beat.
- `docker-compose.prod.yml`: Same services, but API runs without `--reload` (more stable for smoke tests).

## Quickstart (Local Dev)

Prereqs:
- Node.js 20+
- Python 3.11+
- Docker Desktop
- A Supabase project (URL + keys)

1. Configure environment variables

Backend (`backend/.env`):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- Optional: `ADMIN_TOKEN` (guards some maintenance endpoints)

Frontend (`.env.local`):
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_BACKEND_URL` (default used in code: `http://localhost:8000`)
- Optional: `NEXT_PUBLIC_ANALYTICS_SOURCE`

2. Start backend services (Redis + API + worker + beat)

```bash
docker compose up -d redis api worker beat

# Linux-only (optional overrides):
docker compose -f docker-compose.yml -f docker-compose.linux.yml up -d redis api worker beat
```

```powershell
docker compose up -d redis api worker beat
```

API will be on `http://localhost:8000`.

For a more stable run (no FastAPI hot-reload), use:

```bash
docker compose -f docker-compose.prod.yml up -d redis api worker beat

# Linux-only (optional overrides):
docker compose -f docker-compose.prod.yml -f docker-compose.linux.yml up -d redis api worker beat
```

```powershell
docker compose -f docker-compose.prod.yml up -d redis api worker beat
```

3. Start the frontend

```bash
npm install
npm run dev
```

Frontend will be on `http://localhost:3000`.

## Smoke Test (Backend)

Run a minimal API sanity check suite (requires backend running):

```bash
python3 backend/scripts/smoke_test.py
# or:
bash backend/scripts/smoke_test.sh
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File backend/scripts/smoke_test.ps1
```

## Pipeline Test (Scrape + Verify)

Runs one scrape task, polls status, then hits key API endpoints:

```bash
python3 backend/scripts/pipeline_test.py --source inquirer
# or:
bash backend/scripts/pipeline_test.sh --source inquirer
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File backend/scripts/pipeline_test.ps1 -Source inquirer
```

## Manual Scrape (Queue a Scraper Job)

Supported `source` values:
- `inquirer`
- `abs_cbn`
- `gma`
- `philstar`
- `manila_bulletin`
- `rappler`
- `sunstar`
- `manila_times`

Queue a job:

```bash
curl -sS -X POST "http://localhost:8000/scrape/run" \
  -H "Content-Type: application/json" \
  -d '{"source":"inquirer"}'

# Queue multiple scrapers at once
curl -s -X POST "http://localhost:8000/scrape/run" \
  -H "Content-Type: application/json" \
  -d '{"sources":["inquirer","gma","philstar","manila_bulletin","rappler","sunstar","manila_times"]}'
```

```powershell
$run = Invoke-RestMethod "http://localhost:8000/scrape/run" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"source":"inquirer"}'

# Queue multiple scrapers at once
$run = Invoke-RestMethod "http://localhost:8000/scrape/run" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"sources":["inquirer","gma","philstar","manila_bulletin","rappler","sunstar","manila_times"]}'
```

Check status (from the response `jobs[0].task_id`):

```bash
curl -s "http://localhost:8000/scrape/status/<task_id>"
```

```powershell
$taskId = $run.jobs[0].task_id
Invoke-RestMethod "http://localhost:8000/scrape/status/$taskId"
```

## Legacy Root Tools (Archived)

Older one-off scripts (tests, beat monitors, etc.) were moved out of the repo root into `archive/legacy/root_tools/` to keep the root clean. The supported verification flow is `backend/scripts/smoke_test.ps1` and `backend/scripts/pipeline_test.ps1`.

## Common Endpoints

- Health: `GET /`, `GET /health`
- Scraping: `POST /scrape/run`, `GET /scrape/status/{task_id}`
- Articles: `GET /articles`, `GET /articles/home-optimized`, `GET /articles/{article_id}`, `GET /articles/{article_id}/analysis`

## Search Performance (Supabase)

The server-rendered Search (`/search`) and Source pages (`/source/[source]`) can time out if the database must scan
large `content` text fields using `ILIKE %query%` (Postgres error code `57014` / "statement timeout").

Preferred long-term fix: add a full-text search (FTS) tsvector + GIN index, then the frontend will automatically
use `.textSearch("search_tsv", ...)` when available.

- Apply FTS: run `backend/scripts/create_article_search_fts.sql` in Supabase SQL Editor.
- Alternative: run trigram indexes for faster substring `ILIKE` search via `backend/scripts/create_article_search_trgm.sql` (bigger indexes).
- Analytics:
  - `GET /ml/trends?period=7d|30d&source=...`
  - `GET /ml/correlation?period=7d|30d`
  - `GET /ml/entities/top?period=7d|30d`
  - `GET /ml/ner/sample`

## Demo Mode (No Deployed FastAPI)

For thesis demos, you can deploy only the Next.js frontend to Vercel and read precomputed analytics from Supabase:

1. Run these SQL files in the Supabase SQL editor:
   - `backend/scripts/create_entity_rankings_tables.sql`
   - `backend/scripts/create_demo_analytics_tables.sql`
   - `backend/scripts/create_sentiment_report_tables.sql` (optional: enables “Report sentiment” in Quick View)
2. Add GitHub Actions secrets in your repo:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
3. A scheduled GitHub Actions workflow writes **7d** snapshots to Supabase every ~6 hours (see `.github/workflows/analytics_snapshots.yml`).
4. (Optional) You can still write snapshots manually from your machine:

```bash
docker compose exec worker python scripts/entity_rankings_snapshot.py 7d
docker compose exec worker python scripts/trends_snapshot.py 7d
docker compose exec worker python scripts/correlation_snapshot.py 7d
```

The frontend will automatically fall back to Supabase snapshots when `NEXT_PUBLIC_BACKEND_URL` is not usable.

Notes:
- The cron job updates snapshots from whatever data already exists in Supabase. If you want truly “live” updates, you still need a scraper/ML pipeline running somewhere to ingest new articles + sentiment rows.
- 30d snapshots are not generated by the cron workflow by default; the frontend shows a clear empty-state in snapshot mode for 30d.
- If you deploy the frontend to Vercel and you want users to submit “Report sentiment” feedback, add server env vars:
  - `SUPABASE_SERVICE_ROLE_KEY` (server-only; never expose to client)
  - `REPORT_IP_HASH_SALT` (recommended; any random string)

## Supabase Type Safety

Generate/update types:

```bash
supabase gen types typescript --project-id <PROJECT_ID> --schema public > src/types/database.ts
```

```powershell
supabase gen types typescript --project-id <PROJECT_ID> --schema public | Out-File -Encoding utf8 src/types/database.ts
```

## Troubleshooting

- DNS / Supabase resolution issues in Docker:
  - See `[FIX_DNS_ISSUE.md](FIX_DNS_ISSUE.md)`.
- Next.js builds appear “stuck” on Windows:
  - This repo defaults `npm run build` to `next build` (Webpack). Turbopack builds can be extremely slow on some Windows filesystems and can leave long-running Node processes.
  - If you previously ran Turbopack builds, kill the old Node build process and re-run: `npm.cmd run build`.
  - Excluding the repo folder (and `.next/`) from Windows Defender/antivirus can drastically improve build speed.
- Analytics looks "unscored" even though `bias_analysis` has sentiment rows:
  - Supabase/PostgREST commonly caps result sets around ~1000 rows unless you explicitly paginate.
  - Some analytics endpoints batch `bias_analysis` reads using an `IN (article_ids...)` filter; if that batch is too large, older days can look like `Analyzed 0/N` because the response is silently truncated to newer rows.
  - Fix: keep batches small (this repo uses ~250 IDs per request in `backend/app/api/ml_router.py` for `/ml/trends`, `/ml/correlation`, and `/ml/entities/top`).
- Slow local scanning / indexing on Windows:
  - Exclude `node_modules/` and `.next/` in your editor, and avoid recursive searches over them.
- Missing days / partial coverage:
  - Scrapers depend on uptime and site stability. Power interruptions, rate limits, and HTML changes can create gaps.
