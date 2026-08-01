"""Async engine and session factory for Supabase Postgres.

Supabase exposes two ports and they are not interchangeable:

  * 6543 -- transaction-mode pooler (PgBouncer). Server-side prepared
    statements do not survive between transactions, so asyncpg's statement
    cache must be disabled or queries fail intermittently with
    "prepared statement does not exist". Intermittently, because it only
    breaks once a connection is reused across transactions.
  * 5432 -- direct connection. Required for Alembic migrations, which need
    session-level features the pooler does not support.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _normalise(url: str) -> str:
    """Accept the postgres:// URLs Supabase shows in its dashboard."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def is_pooled(url: str) -> bool:
    return ":6543" in url or "pooler.supabase" in url


def create_engine(url: str) -> AsyncEngine:
    connect_args: dict = {}
    kwargs: dict = {"pool_pre_ping": True}

    if is_pooled(url):
        # Both halves matter: disabling the cache stops asyncpg reusing a
        # prepared statement the pooler has already discarded, and the null
        # name generator stops it colliding on names across pooled sessions.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    return create_async_engine(_normalise(url), connect_args=connect_args, **kwargs)


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Supply the Supabase connection string "
                "(port 6543 for the app, 5432 for Alembic)."
            )
        _engine = create_engine(settings.database_url)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency."""
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
