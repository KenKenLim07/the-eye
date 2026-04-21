# Methodology and System Design

This chapter describes the end-to-end design of PH VibeCheck AI—from scheduled ingestion to analytics dashboards—so that the evaluation and results can be interpreted in the correct operational context.

## System Architecture and Deployment

PH VibeCheck AI is implemented as a pipeline for continuous news collection, processing, and visualization. The frontend is a Next.js web application deployed on Vercel [@nextjs; @vercel]. The backend exposes a REST API using FastAPI [@fastapi] and is deployed via Docker [@docker]. Background work (scraping and ML processing) is orchestrated with Celery [@celery] using Redis as broker/cache [@redis]. Articles and analysis outputs are stored in a Supabase-managed PostgreSQL database [@supabase; @postgresql].

![PH VibeCheck AI architecture: Next.js frontend (Vercel), FastAPI backend (Docker), Celery worker/beat with Redis, Supabase (PostgreSQL) storage, and external news sources.](figures/system-flowchart.png){#fig:architecture}

At a high level:
- The Next.js frontend renders dashboards and queries analytics endpoints (e.g., `/ml/*`, `/articles/*`) and/or reads selected listings directly from Supabase.
- The FastAPI backend implements application logic and interacts with Supabase for persistence.
- Celery Beat schedules periodic scraping jobs; Celery workers perform scraping + NLP, then write results back to Supabase tables (e.g., `articles`, `bias_analysis`, `scraping_logs`).

## Web Application Interface (Dashboards)

The web interface is designed to support exploration of:
- recent headlines per source,
- aggregated sentiment trends over time,
- cross-source correlation patterns, and
- entity-level frequency/sentiment summaries.

The home view presents a short system description and provides:
- global search over stored articles,
- one-click source shortcuts (e.g., GMA, ABS-CBN, Inquirer, Philstar, Rappler, Manila Bulletin, Manila Times, Sunstar),
- a KPI snapshot panel (“Today’s pulse”) summarizing operational activity and coverage, and
- a compact “Just in / Happening now” feed showing the most recently ingested articles with sentiment badges and a link to the original source.

TODO (figure): insert an updated home/dashboard screenshot from the latest UI and reference it here (desktop + mobile).
