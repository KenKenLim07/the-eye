# Production Deployment Notes

This project is a Next.js frontend plus a FastAPI backend with Celery workers/beat and Redis, using Supabase (PostgreSQL) for storage.

## Services

- Frontend: Next.js (typically deployed to Vercel)
- Backend API: FastAPI (Docker container)
- Background jobs: Celery worker + Celery beat (Docker containers)
- Broker/cache: Redis (Docker container)
- Database: Supabase (hosted Postgres)

## Environment Variables

Backend (FastAPI/Celery):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL` (example: `redis://redis:6379/0`)
- `CELERY_BROKER_URL` (example: `redis://redis:6379/0`)
- `CELERY_RESULT_BACKEND` (example: `redis://redis:6379/1`)
- `CORS_ALLOW_ORIGINS` (comma-separated list; optional)

Frontend (Next.js):

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_BACKEND_URL`

## Recommended Smoke Checks

- Backend: `GET /health`
- Backend data: `GET /articles/home-optimized?limit_per_source=2&refresh=true`
- Analytics:
  - `GET /ml/trends?period=7d&refresh=true`
  - `GET /ml/correlation?period=7d&refresh=true`
  - `GET /ml/entities/top?period=7d&refresh=true`

## Notes

- Scrapers can fail or produce partial days when sources change layout or when the system is offline; treat missing days as expected operational behavior and rely on `scraping_logs` for traceability.
- Avoid redistributing full publisher article text in public artifacts; store only what is necessary for analysis and provide links to original URLs.

Last updated: March 2026

