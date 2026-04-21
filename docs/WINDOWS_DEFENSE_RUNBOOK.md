# Windows Defense Runbook (Borrowed Laptop)

Goal: run the **full backend stack (Docker)** + optionally the **frontend (Next.js)** on a Windows laptop for final defense, without needing your home desktop.

If you want a shorter “do this tomorrow on my friend’s laptop” checklist, see:
- `docs/BORROWED_LAPTOP_SETUP_GUIDE.md`

## What matters in this repo (quick analysis)

- **Backend is Docker-first**: `redis`, `api` (FastAPI), `worker` (scrapers), `beat` (scheduler), `worker_ml` (sentiment/ML).
- **DistilBERT is not “a local desktop-only thing”**: it runs inside the Docker service `worker_ml`.
- **DistilBERT weights download at first run** (Hugging Face). This repo is set up to persist/cache those files under `./.cache/huggingface` so you can copy them to USB and run offline later.
- The frontend can be either:
  - your **already-live** deployment (simplest for defense), or
  - run locally via `npm run dev` (if the panel wants to see “how it runs” end-to-end).

## One-time setup on the Windows laptop

Install:
- **Docker Desktop** (enable WSL2 backend; Linux containers).
- **Git** (if you will clone).
- **Node.js 20+** (only if you will run the frontend locally).

## Required secrets (bring these on USB)

These are not meant to be committed to GitHub:
- `backend/.env` (Supabase URL + service role key, etc.)
- `.env.local` (frontend env: Supabase anon key, backend URL, etc.)

Tip: for defense, keep a folder on your USB like `secrets/` with copies of both env files.

## Option A (recommended if you have internet): clone + build

PowerShell:

1) Get the code
- `git clone <your-repo-url>`
- `cd the-eye`

2) Put your env files in place
- copy your saved `backend/.env` into `backend/.env`
- copy your saved `.env.local` into `.env.local`

3) Start backend (stable, laptop-friendly)
- `docker compose -f docker-compose.prod.yml -f docker-compose.defense.yml up -d redis api worker_ml`

4) Verify backend quickly
- open `http://localhost:8000/docs`
- or run `powershell -NoProfile -ExecutionPolicy Bypass -File backend/scripts/smoke_test.ps1`

5) (Optional) Run frontend locally
- `npm ci`
- `npm run dev`
- open `http://localhost:3000`

## Option B (best if school internet is unreliable): USB “offline-ish” demo

Do these **at home (on a machine with internet)**:

1) Build backend images
- `docker compose -f docker-compose.prod.yml build`

2) Pre-warm the DistilBERT cache into `./.cache/huggingface`
- `docker compose -f docker-compose.prod.yml run --rm worker_ml python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; mid='distilbert-base-uncased-finetuned-sst-2-english'; AutoTokenizer.from_pretrained(mid); AutoModelForSequenceClassification.from_pretrained(mid); print('HF cache ready')"`

3) Export Docker images to a tar (copy to USB)
- `docker pull redis:7-alpine`
- `docker image save -o ph-eye-images.tar redis:7-alpine ph-eye-backend:local`

4) Copy to USB
- whole project folder (so it’s “plug and play”), including `./.cache/huggingface`
- `ph-eye-images.tar`
- your `backend/.env` + `.env.local`

On the **borrowed Windows laptop**:

1) Copy the project folder from USB to a local drive (recommended: under `C:\\Users\\<name>\\...`).

2) Load images
- `docker load -i ph-eye-images.tar`

3) Put env files in place
- `backend/.env`
- `.env.local`

4) Start backend
- `docker compose -f docker-compose.prod.yml -f docker-compose.defense.yml up -d redis api worker_ml`

5) (Optional) Force “offline-only” transformer loads (after cache is pre-warmed)
- PowerShell (same terminal before `docker compose up`):
  - `$env:TRANSFORMERS_OFFLINE=1`
  - `$env:HF_HUB_OFFLINE=1`

## What to show the panel (quick demo flow)

- `docker ps` (show containers running)
- `http://localhost:8000/docs` (show FastAPI Swagger UI)
- `backend/scripts/smoke_test.ps1` (shows real endpoints are working)
- Open the repo in VS Code (show `docker-compose.prod.yml`, `backend/app/main.py`, and `backend/app/ml/sentiment_transformer.py` to explain where DistilBERT runs)
