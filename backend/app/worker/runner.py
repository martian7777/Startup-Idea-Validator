"""In-process job execution with a durable event log.

Behind the `JobRunner` protocol so this can be swapped for arq or Celery
without touching the API layer. Two properties matter more than throughput:

  * Every progress event is written to Postgres before it is broadcast, so a
    client that connects late or reconnects replays the full history.
  * A run left `running` when the process dies is marked `interrupted` at the
    next startup. An in-process worker cannot outlive its process, and a run
    that hangs in `running` forever is worse than one that visibly failed.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run, RunEvent, RunStatus

logger = logging.getLogger(__name__)


class EventBus:
    """Fan-out of run events to connected SSE clients.

    Subscribers get their own bounded queue. A slow reader is dropped rather
    than allowed to apply backpressure to the run itself -- the durable log
    means it loses nothing it cannot replay on reconnect.
    """

    def __init__(self, max_queue: int = 256) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue]] = defaultdict(set)
        self._max_queue = max_queue

    def subscribe(self, run_id: UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: UUID, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id)
        if not subs:
            return
        subs.discard(queue)
        if not subs:
            self._subscribers.pop(run_id, None)

    def publish(self, run_id: UUID, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(run_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping event for slow SSE subscriber on run %s", run_id)


class RunRecorder:
    """Writes progress to the durable log, then broadcasts it."""

    def __init__(self, run_id: UUID, sessionmaker: async_sessionmaker[AsyncSession], bus: EventBus):
        self._run_id = run_id
        self._sessionmaker = sessionmaker
        self._bus = bus
        self._seq = 0
        self._lock = asyncio.Lock()

    async def emit(self, node: str, phase: str, payload: dict | None = None) -> None:
        async with self._lock:
            seq = self._seq
            self._seq += 1

        async with self._sessionmaker() as session:
            session.add(
                RunEvent(
                    run_id=self._run_id, seq=seq, node=node, phase=phase, payload=payload
                )
            )
            await session.commit()

        # Published only after the write, so a replay can never lag a live event.
        self._bus.publish(
            self._run_id,
            {"seq": seq, "node": node, "phase": phase, "payload": payload},
        )


class JobRunner(Protocol):
    async def submit(self, run_id: UUID) -> None: ...


class AsyncioJobRunner:
    """Runs validation jobs as asyncio tasks in the API process."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        bus: EventBus,
        execute: Any,
        max_concurrent_runs: int = 3,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._bus = bus
        self._execute = execute
        self._tasks: dict[UUID, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)

    async def submit(self, run_id: UUID) -> None:
        if run_id in self._tasks:
            return
        task = asyncio.create_task(self._run(run_id), name=f"run-{run_id}")
        self._tasks[run_id] = task
        # Keeps a completed task from lingering in the dict forever.
        task.add_done_callback(lambda _t, rid=run_id: self._tasks.pop(rid, None))

    async def _run(self, run_id: UUID) -> None:
        recorder = RunRecorder(run_id, self._sessionmaker, self._bus)
        async with self._semaphore:
            await self._set_status(run_id, RunStatus.RUNNING, started=True)
            try:
                await self._execute(run_id, recorder)
                await self._set_status(run_id, RunStatus.COMPLETED, finished=True)
                await recorder.emit("run", "completed")
            except asyncio.CancelledError:
                await self._set_status(
                    run_id, RunStatus.INTERRUPTED, finished=True, error="Run cancelled."
                )
                raise
            except Exception as exc:  # surfaced to the founder, not swallowed
                logger.exception("Run %s failed", run_id)
                await self._set_status(
                    run_id, RunStatus.FAILED, finished=True, error=f"{type(exc).__name__}: {exc}"
                )
                await recorder.emit("run", "failed", {"error": str(exc)})

    async def _set_status(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        started: bool = False,
        finished: bool = False,
        error: str | None = None,
    ) -> None:
        from datetime import datetime, timezone

        values: dict[str, Any] = {"status": status.value}
        now = datetime.now(timezone.utc)
        if started:
            values["started_at"] = now
        if finished:
            values["finished_at"] = now
        if error is not None:
            values["error"] = error

        async with self._sessionmaker() as session:
            await session.execute(update(Run).where(Run.id == run_id).values(**values))
            await session.commit()

    async def shutdown(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)


async def reap_interrupted_runs(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Mark runs orphaned by a previous process as interrupted.

    Called at startup. Without it, a restart leaves runs stuck in `running`
    with nothing left alive to advance them.
    """
    async with sessionmaker() as session:
        result = await session.execute(
            select(Run.id).where(Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]))
        )
        orphaned = [row[0] for row in result]
        if not orphaned:
            return 0

        await session.execute(
            update(Run)
            .where(Run.id.in_(orphaned))
            .values(
                status=RunStatus.INTERRUPTED.value,
                error="Server restarted while this run was in progress.",
            )
        )
        await session.commit()

    logger.warning("Marked %d orphaned run(s) as interrupted", len(orphaned))
    return len(orphaned)
