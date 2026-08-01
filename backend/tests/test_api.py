"""API and job-lifecycle tests against SQLite.

Runs the real routes, the real job runner, and the real event log with a stub
executor in place of the agents, so the whole run lifecycle is exercised
without a Gemini key or a Supabase instance.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import runs as runs_route
from app.config import get_settings
from app.db.models import Base, Run, RunStatus
from app.db.session import get_session
from app.worker.runner import AsyncioJobRunner, EventBus, reap_interrupted_runs

SUBMISSION = {
    "idea": "A tool that tracks differing university application requirements",
    "target_customer": "International master's applicants",
    "country": "Germany",
    "industry": "Education technology",
    "revenue_model": "subscription",
}


@pytest_asyncio.fixture
async def sessionmaker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


def build_app(sessionmaker, execute):
    """App wired without the production lifespan (no Supabase, no reaper)."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(runs_route.router)

    bus = EventBus()
    app.state.sessionmaker = sessionmaker
    app.state.event_bus = bus
    app.state.job_runner = AsyncioJobRunner(sessionmaker, bus, execute)

    async def override_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return app


@pytest_asyncio.fixture
async def client_factory(sessionmaker):
    created = []

    def make(execute):
        app = build_app(sessionmaker, execute)
        created.append(app)
        return AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    yield make

    for app in created:
        await app.state.job_runner.shutdown()


async def happy_executor(run_id, recorder):
    await recorder.emit("manager", "started")
    await recorder.emit("manager", "completed")
    await recorder.emit("reporter", "completed", {"ok": True})


async def failing_executor(run_id, recorder):
    raise RuntimeError("search budget exhausted")


# --- Submission and history ----------------------------------------------


@pytest.mark.asyncio
async def test_create_run_returns_id_and_queues_work(client_factory):
    async with client_factory(happy_executor) as client:
        response = await client.post("/api/runs", json=SUBMISSION)
        assert response.status_code == 201
        assert response.json()["id"]


@pytest.mark.asyncio
async def test_submission_is_validated(client_factory):
    async with client_factory(happy_executor) as client:
        response = await client.post("/api/runs", json={**SUBMISSION, "idea": "too short"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_run_reaches_completed(client_factory, sessionmaker):
    async with client_factory(happy_executor) as client:
        run_id = (await client.post("/api/runs", json=SUBMISSION)).json()["id"]
        await asyncio.sleep(0.3)

        run = await client.get(f"/api/runs/{run_id}")
        assert run.json()["status"] == RunStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_failure_is_recorded_not_swallowed(client_factory):
    async with client_factory(failing_executor) as client:
        run_id = (await client.post("/api/runs", json=SUBMISSION)).json()["id"]
        await asyncio.sleep(0.3)

        body = (await client.get(f"/api/runs/{run_id}")).json()
        assert body["status"] == RunStatus.FAILED.value
        assert "search budget exhausted" in body["error"]


@pytest.mark.asyncio
async def test_history_lists_runs(client_factory):
    async with client_factory(happy_executor) as client:
        await client.post("/api/runs", json=SUBMISSION)
        await asyncio.sleep(0.2)

        listed = (await client.get("/api/runs")).json()
        assert len(listed) == 1
        assert listed[0]["idea"].startswith("A tool that tracks")


@pytest.mark.asyncio
async def test_missing_run_and_report_return_404(client_factory):
    async with client_factory(happy_executor) as client:
        missing = uuid.uuid4()
        assert (await client.get(f"/api/runs/{missing}")).status_code == 404
        assert (await client.get(f"/api/runs/{missing}/report")).status_code == 404


# --- Durable event log ----------------------------------------------------


@pytest.mark.asyncio
async def test_stream_replays_the_log_after_the_run_finished(client_factory):
    """A client connecting late must still receive the full history."""
    async with client_factory(happy_executor) as client:
        run_id = (await client.post("/api/runs", json=SUBMISSION)).json()["id"]
        await asyncio.sleep(0.3)

        async with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
            body = ""
            async for chunk in response.aiter_text():
                body += chunk
                if "event: done" in body:
                    break

        nodes = [
            json.loads(line[len("data: ") :])["node"]
            for line in body.splitlines()
            if line.startswith("data: ") and '"node"' in line
        ]
        assert "manager" in nodes
        assert "reporter" in nodes
        assert "event: done" in body


@pytest.mark.asyncio
async def test_events_are_sequenced_without_gaps(client_factory, sessionmaker):
    from sqlalchemy import select

    from app.db.models import RunEvent

    async with client_factory(happy_executor) as client:
        run_id = (await client.post("/api/runs", json=SUBMISSION)).json()["id"]
        await asyncio.sleep(0.3)

        async with sessionmaker() as session:
            result = await session.execute(
                select(RunEvent.seq)
                .where(RunEvent.run_id == uuid.UUID(run_id))
                .order_by(RunEvent.seq)
            )
            seqs = [row[0] for row in result]

    assert seqs == list(range(len(seqs)))


# --- Restart recovery -----------------------------------------------------


@pytest.mark.asyncio
async def test_orphaned_runs_are_marked_interrupted_on_startup(sessionmaker):
    """An in-process worker dies with the process; a stuck run must not persist."""
    async with sessionmaker() as session:
        session.add_all(
            [
                Run(
                    user_id=uuid.uuid4(),
                    submission=SUBMISSION,
                    status=RunStatus.RUNNING.value,
                ),
                Run(
                    user_id=uuid.uuid4(),
                    submission=SUBMISSION,
                    status=RunStatus.QUEUED.value,
                ),
                Run(
                    user_id=uuid.uuid4(),
                    submission=SUBMISSION,
                    status=RunStatus.COMPLETED.value,
                ),
            ]
        )
        await session.commit()

    assert await reap_interrupted_runs(sessionmaker) == 2

    from sqlalchemy import select

    async with sessionmaker() as session:
        statuses = sorted(
            row[0] for row in await session.execute(select(Run.status))
        )
    assert statuses == ["completed", "interrupted", "interrupted"]


@pytest.mark.asyncio
async def test_reaper_is_a_noop_when_nothing_is_orphaned(sessionmaker):
    assert await reap_interrupted_runs(sessionmaker) == 0


# --- Event bus ------------------------------------------------------------


def test_slow_subscriber_is_dropped_not_backpressured():
    """A stalled browser must never be able to stall the run itself."""
    bus = EventBus(max_queue=2)
    run_id = uuid.uuid4()
    queue = bus.subscribe(run_id)

    for i in range(10):
        bus.publish(run_id, {"seq": i})

    assert queue.qsize() == 2  # overflow discarded, no exception raised


def test_unsubscribe_cleans_up():
    bus = EventBus()
    run_id = uuid.uuid4()
    queue = bus.subscribe(run_id)
    bus.unsubscribe(run_id, queue)
    bus.publish(run_id, {"seq": 0})  # must not raise
    assert queue.empty()
