"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    @app.middleware("http")
    async def security_boundary(request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_body_bytes:
                    return JSONResponse({"detail": "Request body too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        if settings.environment.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response
    app.include_router(runs.router)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
