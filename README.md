# PH VibeCheck AI

PH VibeCheck AI is a full-stack capstone project that continuously collects Philippine online news, runs lightweight NLP (sentiment + NER), and renders dashboards for trends, correlation, entities, and per-source browsing.

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

2. Start backend services (Redis + API + workers + beat)

```bash
docker compose up -d redis api worker beat

# Optional (only if you force headed Playwright for ABS-CBN):
# By default ABS-CBN uses an API fast-path and does NOT need a headed worker.
# Start this only when debugging / if ABS-CBN changes and you set `ABS_CBN_FORCE_HEADED=1`.
docker compose up -d worker_headed

# Linux-only (optional overrides):
docker compose -f docker-compose.yml -f docker-compose.linux.yml up -d redis api worker beat
```

```powershell
docker compose up -d redis api worker beat

# Optional (only if you force headed Playwright for ABS-CBN):
docker compose up -d worker_headed
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

### ABS-CBN note (Akamai / headed Chromium)

ABS-CBN blocks plain HTTP requests to article pages (often `403`), and may block Playwright **headless** Chromium.

This repo now supports an **API content fast-path** (preferred): it pulls article bodies from the public OneDomain API (`od2-content-api.abs-cbn.com`) and can run on the normal headless scrape worker without launching a browser.

Deep dive / playbook: `abscbn.md`.

Env flags (optional; defaults shown are what the repo expects):
- `ABS_CBN_API_DISCOVERY=1` discover links via `od2-content-api` (default `1`)
- `ABS_CBN_API_LIST_URLS=...` comma-separated list endpoints (default: news/business/technology/sports/entertainment lists)
- `ABS_CBN_API_CONTENT_FASTPATH=1` build articles from `body_html` (default `1`)
- `ABS_CBN_API_MIN_BODY_CHARS=600` minimum body length to accept (default `600`)

Headed Playwright remains available as a fallback if ABS-CBN changes:
- Service: `worker_headed` (runs under `xvfb-run` inside Docker; no browser window appears on your host)
- Queue: `scrape_headed`
- Force it by setting `ABS_CBN_FORCE_HEADED=1`

To enable scheduled runs (optional), set `ENABLE_ABS_CBN_SCRAPER=1` in `backend/.env`. You only need `worker_headed` running if you set `ABS_CBN_FORCE_HEADED=1`.

Canary (optional): validate the API endpoints/fields we rely on:

```bash
python backend/scripts/abs_cbn_api_canary.py
```

### GMA fast-path (HTTP + JSON-LD) + network debug

GMA supports an HTTP-first fast-path that avoids rendering:
- **Best case:** fetch the same article “blob” the site loads over XHR: `https://data.gmanetwork.com/<code>/gno/story/<id>.gz`
- Fallback: JSON-LD in the raw HTML
- Final fallback: Playwright DOM scrape (headless)

Env flags (set on the `worker` container or inline in the command):
- `GMA_HTTP_FASTPATH=1` enables the HTTP fast-path (default `1` in this repo)
- `GMA_HTTP_DISCOVERY=1` discovers candidate links via plain HTTP (no Playwright) when fast-path is enabled (default `1`)
- `GMA_HTTP_MIN_BODY_CHARS=600` minimum JSON-LD body length to accept (default `600`)
- `GMA_STORY_API_FASTPATH=1` tries GMA’s internal `data.gmanetwork.com/.../story/<id>.gz` payload (default `1`)
- `GMA_STORY_API_CODES=227,394` candidate GMA story API codes to try by story id (default `227,394`)
- `GMA_HTTP_TIMEOUT_CONNECT_S=5`, `GMA_HTTP_TIMEOUT_READ_S=15` HTTP timeout tuning (defaults shown)
- `GMA_NETWORK_DEBUG=1` logs JSON/XHR endpoints observed while loading a page (default `0`)
- `GMA_NETWORK_DEBUG_MAX=30` max captured responses (default `30`)

Examples:

```bash
# Run GMA with the fast-path enabled
docker compose exec worker sh -lc 'GMA_HTTP_FASTPATH=1 python -c "from app.scrapers.gma import GMAScraper; r=GMAScraper().scrape_latest(max_articles=1); print(r.metadata); print(r.errors)"'

# Debug a single GMA URL and print observed JSON/XHR endpoints
docker compose exec worker sh -lc 'GMA_NETWORK_DEBUG=1 python -c "from app.scrapers.gma import debug_gma_url; print(debug_gma_url(\"https://www.gmanetwork.com/news/topstories/nation/123456/example-story/\"))"'
```

Tip: when `GMA_NETWORK_DEBUG=1`, look for endpoints shaped like:
- `https://data.gmanetwork.com/<code>/gno/story/<id>.gz` ← full article payload (best)
If you see a new `<code>`, append it to `GMA_STORY_API_CODES`.

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
