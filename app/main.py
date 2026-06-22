"""FastAPI application factory."""

from fastapi import FastAPI

from app.api import jobs, models


def create_app() -> FastAPI:
    app = FastAPI(
        title="Transaction Processing Pipeline",
        description="Async pipeline that ingests, cleans, classifies, and reports on transaction CSVs.",
        version="1.0.0",
    )

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(jobs.router)
    app.include_router(models.router)
    return app


app = create_app()
