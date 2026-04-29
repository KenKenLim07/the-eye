# Appendix F — User Guide (Quick Start)

This appendix provides a practical guide for running PH VibeCheck AI for demonstration and evaluation.

## Repository

Source code repository (clone URL):
- `https://github.com/KenKenLim07/the-eye`

## Prerequisites

This guide assumes:
- Git
- Docker + Docker Compose (Docker Desktop on Windows/macOS, or Docker Engine + Compose plugin on Linux)
- Node.js (LTS recommended) and npm (for the frontend dev server)
- A Supabase project (credentials are required for the backend and UI to run)

Note: you do not need to install Python locally if you run the backend and workers via Docker.

## Clone the project

```bash
git clone https://github.com/KenKenLim07/the-eye.git
cd the-eye
```

## Configure environment variables (do not commit keys)

### Frontend (`.env.local`)

Create `.env.local` in the repository root:

```bash
# Supabase (frontend)
NEXT_PUBLIC_SUPABASE_URL="https://<project-ref>.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="<your-anon-key>"

# Optional: set explicitly in production; in dev, the app defaults to localhost.
NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"
```

### Backend (`backend/.env`)

Create `backend/.env`:

```bash
# Supabase (backend)
SUPABASE_URL="https://<project-ref>.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="<your-service-role-key>"
```

Note: `SUPABASE_SERVICE_ROLE_KEY` is sensitive. It is required by the backend workers for scraping/ML writes and evaluation scripts.

## Start the system (Docker services)

From the repository root:

```bash
docker compose up -d redis api worker worker_ml beat
```

Verify services:

```bash
docker compose ps
docker compose logs -f api
```

## Run the frontend (local dev)

```bash
npm install
npm run dev
```

Open the app at the URL printed by the dev server (commonly `http://localhost:3000`).

## Basic usage (UI)

The dashboards are designed for exploration and verification:
- **Home:** recent articles and overall status snapshot.
- **Trends:** view daily sentiment trends by source for a chosen window.
- **Correlation:** compare sources via correlation of daily average sentiment.
- **Entities:** view frequently mentioned entities and associated sentiment signals.
- **Search:** keyword search with drill-down to individual articles for verification.

## Collect new articles (scraping)

You can trigger scraping via the backend API (example: GMA):

```bash
curl -sS -X POST "http://localhost:8000/scrape/run" \
  -H "Content-Type: application/json" \
  -d '{"source":"gma"}'
```

To observe scraper execution:

```bash
docker compose logs -f worker
```

## Run ML analysis / backfill

To rescore recent content (example: last 7 days):

```bash
docker compose exec worker_ml python /app/scripts/backfill_ml_analysis.py --days 7 --batch-size 200 --force
```

Monitor ML progress:

```bash
docker compose logs -f worker_ml
```

## Evaluation (gold sets and benchmark)

Key commands used for evaluation are listed in:
- `thesis-hardbound/chapters/A_appendix_commands_repro.md`
- `docs/ACCURACY_EVALUATION.md`

## Common troubleshooting

**No data appears in Trends/Correlation/Entities (frontend):**
- Check browser console for CORS errors.
- Ensure the `api` container is running and was restarted after configuration changes:
  - `docker compose up -d --force-recreate api`

**Transformer downloads fail or are slow:**
- Pre-create the HF cache directory on the host: `mkdir -p ~/.cache/huggingface`
- Use offline mode once cached: `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`

**Worker appears “stuck” during backfills:**
- Long-form articles and network timeouts can slow batches.
- Check `docker compose logs -f worker_ml` for retries/timeouts and confirm CPU usage.
