"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import runs
from app.config import get_settings
from app.db.session import dispose_engine, get_sessionmaker
from app.worker.execute import RunExecutor
from app.worker.runner import AsyncioJobRunner, EventBus, reap_interrupted_runs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY is not set - runs will fail at the first agent.")

    sessionmaker = get_sessionmaker()
    bus = EventBus()
    executor = RunExecutor(settings, sessionmaker)
    job_runner = AsyncioJobRunner(sessionmaker, bus, executor)

    app.state.sessionmaker = sessionmaker
    app.state.event_bus = bus
    app.state.job_runner = job_runner

    # This process is the only thing that can advance a run, so anything left
    # mid-flight by a previous process is dead and must be marked as such.
    reaped = await reap_interrupted_runs(sessionmaker)
    if reaped:
        logger.warning("Marked %d run(s) interrupted after restart", reaped)

    try:
        yield
    finally:
        await job_runner.shutdown()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Startup Idea Validator", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(runs.router)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "grounding_enabled": settings.grounding_available,
            "models": {
                "extract": settings.model_extract,
                "research": settings.model_research,
                "critic": settings.model_critic,
            },
            "search_budget": {
                "per_agent": settings.max_searches_per_agent,
                "per_run": settings.max_searches_per_run,
            },
        }

    return app


app = create_app()
