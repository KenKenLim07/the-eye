from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.articles_router import router as articles_router
from app.api.cache_router import router as cache_router
from app.api.health_router import router as health_router
from app.api.ml_router import router as ml_router
from app.api.scrape_router import router as scrape_router


def _split_csv_env(name: str) -> list[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def create_app() -> FastAPI:
    app = FastAPI(title="PH VibeCheck AI Backend", version="0.1.0")

    # Keep CORS config identical to previous main.py to avoid frontend breakage.
    # NOTE: browsers treat different ports as different origins; during `npm run dev`
    # the port can change (3000/3001/3002/etc.). To avoid silent CORS failures, we
    # allow localhost + 127.0.0.1 on any port by default via regex, while still
    # supporting explicit additional origins via env var.
    allow_origin_regex = (os.getenv("CORS_ALLOW_ORIGIN_REGEX") or "").strip() or r"^https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?$"
    allow_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        *_split_csv_env("CORS_ALLOW_ORIGINS"),
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # No prefixes: routes must remain identical.
    app.include_router(health_router)
    app.include_router(scrape_router)
    app.include_router(ml_router)
    app.include_router(articles_router)
    app.include_router(cache_router)
    return app


# Uvicorn entrypoint compatibility: `uvicorn app.main:app`
app = create_app()
