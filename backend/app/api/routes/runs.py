"""Run submission, polling, streaming, and report retrieval."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.db.models import Report, Run, RunEvent, RunStatus
from app.db.session import get_session
from app.schemas.contracts import IdeaSubmission

router = APIRouter(prefix="/api/runs", tags=["runs"])

TERMINAL = {RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.INTERRUPTED.value}


class RunCreated(BaseModel):
    id: UUID
    status: str


class RunSummary(BaseModel):
    id: UUID
    status: str
    score_total: float | None
    score_band: str | None
    idea: str
    created_at: str
    error: str | None = None


@router.post("", response_model=RunCreated, status_code=201)
async def create_run(
    submission: IdeaSubmission,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RunCreated:
    settings = get_settings()
    run = Run(
        user_id=UUID(settings.dev_user_id),
        submission=submission.model_dump(mode="json"),
        status=RunStatus.QUEUED.value,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    await request.app.state.job_runner.submit(run.id)
    return RunCreated(id=run.id, status=run.status)


@router.get("", response_model=list[RunSummary])
async def list_runs(
    limit: int = Query(default=25, ge=1, le=100), session: AsyncSession = Depends(get_session)
) -> list[RunSummary]:
    result = await session.execute(select(Run).order_by(desc(Run.created_at)).limit(limit))
    return [
        RunSummary(
            id=r.id,
            status=r.status,
            score_total=r.score_total,
            score_band=r.score_band,
            idea=str(r.submission.get("idea", ""))[:200],
            created_at=r.created_at.isoformat(),
            error=r.error,
        )
        for r in result.scalars()
    ]


@router.get("/{run_id}")
async def get_run(run_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return {
        "id": str(run.id),
        "status": run.status,
        "submission": run.submission,
        "score_total": run.score_total,
        "score_band": run.score_band,
        "usage": run.usage,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/{run_id}/report")
async def get_report(run_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(select(Report).where(Report.run_id == run_id))
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(404, "No report yet for this run")
    return {"content": report.content, "score": report.score, "markdown": report.markdown}


@router.get("/{run_id}/stream")
async def stream_run(run_id: UUID, request: Request) -> EventSourceResponse:
    """Replay the durable event log, then tail live events.

    Replaying first is what makes a refresh or a late connection safe: the
    client always sees the full history rather than joining blind.
    """
    bus = request.app.state.event_bus
    sessionmaker = request.app.state.sessionmaker
    queue = bus.subscribe(run_id)

    async def publisher():
        try:
            async with sessionmaker() as session:
                run = await session.get(Run, run_id)
                if run is None:
                    yield {"event": "error", "data": json.dumps({"error": "Run not found"})}
                    return

                result = await session.execute(
                    select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.seq)
                )
                replayed = -1
                for event in result.scalars():
                    replayed = event.seq
                    yield {
                        "event": "progress",
                        "data": json.dumps(
                            {
                                "seq": event.seq,
                                "node": event.node,
                                "phase": event.phase,
                                "payload": event.payload,
                            }
                        ),
                    }

                if run.status in TERMINAL:
                    yield {"event": "done", "data": json.dumps({"status": run.status})}
                    return

            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Keeps proxies from closing an idle stream during a long
                    # grounded search.
                    yield {"event": "ping", "data": "{}"}
                    continue

                # Skip anything the replay already delivered.
                if event["seq"] <= replayed:
                    continue

                yield {"event": "progress", "data": json.dumps(event)}
                if event["node"] == "run" and event["phase"] in {"completed", "failed"}:
                    yield {"event": "done", "data": json.dumps({"status": event["phase"]})}
                    return
        finally:
            bus.unsubscribe(run_id, queue)

    return EventSourceResponse(publisher())
