from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.articles_router import router as articles_router
from app.api.bias_router import router as bias_router
from app.api.cache_router import router as cache_router
from app.api.health_router import router as health_router
from app.api.ml_router import router as ml_router
from app.api.scrape_router import router as scrape_router


def create_app() -> FastAPI:
    app = FastAPI(title="PH Eye Backend", version="0.1.0")

    # Keep CORS config identical to previous main.py to avoid frontend breakage.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # No prefixes: routes must remain identical.
    app.include_router(health_router)
    app.include_router(scrape_router)
    app.include_router(ml_router)
    app.include_router(articles_router)
    app.include_router(bias_router)
    app.include_router(cache_router)
    return app


# Uvicorn entrypoint compatibility: `uvicorn app.main:app`
app = create_app()
