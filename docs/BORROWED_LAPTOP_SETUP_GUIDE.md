# Borrowed Laptop Setup Guide (Online Demo + Local Frontend)

Use this on your friend’s Windows laptop **once** (before final defense) so on defense day you only need to start Docker + open the app.

Your plan (recommended):
- Demo **local frontend** (`http://localhost:3000`) + **local backend** (`http://localhost:8000`)
- Optionally also open the **live Vercel frontend** as a backup/extra proof

## Bring these on USB (important)

- `backend/.env` (Supabase URL + service role key + any other backend secrets)
- `.env.local` (frontend env: Supabase anon key, backend URL, etc.)

Do **not** rely on GitHub for these files.

## 1) Install prerequisites (one-time)

Install on the laptop:
- Docker Desktop (WSL2 backend, Linux containers)
- Git for Windows
- Node.js 20+ (only if running frontend locally)

Reboot if Docker/WSL asks.

## 2) Clone the repo

PowerShell:
- `cd C:\`
- `mkdir Projects` (if you don’t have it yet)
- `cd .\Projects\`
- `git clone <your-repo-url> the-eye`
- `cd .\the-eye\`

## 3) Put env files in place

Copy your USB versions into the repo:
- `backend\.env`
- `.env.local`

## 4) Start backend (recommended minimal services)

This runs FastAPI + Redis + the ML worker (DistilBERT/Hybrid sentiment).

- (Optional, but recommended on a fast connection) build once so you don’t wait later:
  - `docker compose -f docker-compose.prod.yml build`
- `docker compose -f docker-compose.prod.yml -f docker-compose.defense.yml up -d redis api worker_ml`

Quick checks:
- `docker ps`
- open `http://localhost:8000/docs`
- run: `powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\smoke_test.ps1`

### One-time: force-download the DistilBERT model (so it’s ready on defense day)

This downloads weights into `./.cache/huggingface` (persisted by this repo).

- `docker compose -f docker-compose.prod.yml run --rm worker_ml python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; mid='distilbert-base-uncased-finetuned-sst-2-english'; AutoTokenizer.from_pretrained(mid); AutoModelForSequenceClassification.from_pretrained(mid); print('HF cache ready')"`

## 5) Start frontend (choose one)

### Option A (simplest): use the already-live frontend

Nothing to install/run locally. Demo the live site and point it to your local backend if needed (depends on your `.env.local` / deployment setup).

### Option B: run frontend locally (you said you’ll do this)

- `npm ci`
- `npm run dev`
- open `http://localhost:3000`

## 6) Pre-warm DistilBERT (do this while you still have internet)

Your repo is configured to persist Hugging Face downloads under:
- `./.cache/huggingface`

So once the ML worker downloads the model, future runs are faster and can work even with weak internet.

Easiest way: after you start `worker_ml`, let it run for a few minutes and hit any ML endpoint once:
- `http://localhost:8000/ml/trends?period=7d&include_today=true&refresh=true`

## 7) Optional: start scrapers + scheduler (only if you’ll demo scraping)

- `docker compose -f docker-compose.prod.yml up -d worker beat`

## Defense-day “just run it” commands

From the repo root:
- `docker compose -f docker-compose.prod.yml -f docker-compose.defense.yml up -d`
- open `http://localhost:8000/docs`
- `npm run dev`

## Docker images: what to do with them?

For an online demo (internet available):
- You can simply build on the laptop once and keep the images there:
  - `docker compose -f docker-compose.prod.yml build`
  - then use `docker compose ... up -d`
- Docker Desktop keeps built images until you uninstall Docker or run a cleanup/prune.

If you want a safety net (optional), export images to USB after the build:
- `docker pull redis:7-alpine`
- `docker image save -o ph-eye-images.tar redis:7-alpine ph-eye-backend:local`
- Later on any machine: `docker load -i ph-eye-images.tar`

## About the “snapshots” (GitHub cron / Actions)

This repo has scheduled GitHub Actions that write analytics snapshots into Supabase:
- `.github/workflows/analytics_snapshots.yml`
- `.github/workflows/entity-rankings-snapshot.yml`

You don’t need to run these on the defense laptop; they’re just good to mention/show as part of your system design.

For a more reliable offline-style backup kit (only if you really need it), see `docs/WINDOWS_DEFENSE_RUNBOOK.md`.
- Make a “backup kit” on USB: a Docker image tar + the Hugging Face cache folder.

### Backup kit (step-by-step)

Do this **at home (with internet)** on any machine that can run Docker:

1) Build the backend image (creates `ph-eye-backend:local`)
- `docker compose -f docker-compose.prod.yml build`

2) Pre-warm the DistilBERT weights into `./.cache/huggingface`
- `docker compose -f docker-compose.prod.yml run --rm worker_ml python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; mid='distilbert-base-uncased-finetuned-sst-2-english'; AutoTokenizer.from_pretrained(mid); AutoModelForSequenceClassification.from_pretrained(mid); print('HF cache ready')"`

3) Export Docker images to a tar (copy to USB)
- `docker pull redis:7-alpine`
- `docker image save -o ph-eye-images.tar redis:7-alpine ph-eye-backend:local`

4) Copy these to USB
- `ph-eye-images.tar`
- the folder `./.cache/huggingface`
- your secrets: `backend/.env` and `.env.local`

On the **borrowed Windows laptop** (even if internet is weak/unavailable):

1) Copy the project folder from USB to local disk (recommended), then `cd` into it
- Example: `C:\Projects\the-eye\`

2) Load images
- `docker load -i ph-eye-images.tar`

3) (Optional) Force offline-only transformer loads (only after step 2 + HF cache copy)
- `$env:TRANSFORMERS_OFFLINE=1`
- `$env:HF_HUB_OFFLINE=1`

4) Start backend
- `docker compose -f docker-compose.prod.yml -f docker-compose.defense.yml up -d redis api worker_ml`

5) Verify
- open `http://localhost:8000/docs`
- or run `powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\smoke_test.ps1`
