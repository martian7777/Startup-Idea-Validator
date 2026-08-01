"""Drives the ADK graph for one run and assembles the scored report.

The ordering here encodes the product's central rule: the report agent writes
prose, then the deterministic scorer computes the number, then the two are
stored together. The scorer never sees the report's rhetoric and the report
agent never sees the score, so neither can be tuned to agree with the other.

Attribution is verified before scoring, not after: a claim citing a URL that
search never retrieved is stripped of its source and downgraded, which lowers
the evidence coverage feeding the score.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from google.adk.runners import InMemoryRunner
from google.genai import types
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.agents.pipeline import PROGRESS_STAGES, build_pipeline
from app.config import Settings
from app.db.models import Evidence, Report, Run
from app.llm.budget import RunBudget
from app.llm.grounding import SourceRef, verify_attribution
from app.schemas.contracts import IdeaSubmission
from app.schemas.evidence import Claim, ClaimKind, EvidenceLedger, EvidenceStrength
from app.scoring.scorer import (
    CategoryRating,
    OpportunityScore,
    apply_critic_overrides,
    compute_score,
)

logger = logging.getLogger(__name__)

APP_NAME = "startup_validator"


def collect_ratings(*outputs: Any) -> list[CategoryRating]:
    """Gather category ratings proposed across agent outputs.

    Where two agents rate the same category, the lower rating wins -- a
    disagreement is itself a signal of weak evidence, and taking the optimistic
    reading would let one agent's enthusiasm override another's caution.
    """
    best: dict[Any, CategoryRating] = {}
    for output in outputs:
        for rating in getattr(output, "ratings", None) or []:
            existing = best.get(rating.category)
            if existing is None or rating.rating < existing.rating:
                best[rating.category] = rating
    return list(best.values())


def build_ledger(
    outputs: list[Any], retrieved: dict[str, list[SourceRef]]
) -> tuple[EvidenceLedger, list[str]]:
    """Merge claims from all branches, verifying every citation.

    Runs after the join, single-threaded, precisely because concurrent writes
    to one ledger would race.
    """
    all_sources: list[SourceRef] = [s for sources in retrieved.values() for s in sources]
    ledger = EvidenceLedger()
    fabricated: list[str] = []

    for output in outputs:
        for field in ("problem_evidence", "demand_signals", "trends", "evidence"):
            for claim in getattr(output, field, None) or []:
                ledger.add(_verified(claim, all_sources, fabricated))

    return ledger, fabricated


def _verified(claim: Claim, sources: list[SourceRef], fabricated: list[str]) -> Claim:
    """Strip and downgrade any citation search did not actually retrieve."""
    if not claim.source_url:
        return claim

    verified, invented = verify_attribution([claim.source_url], sources)
    if verified:
        return claim

    fabricated.extend(invented)
    logger.warning("Unverifiable citation dropped: %s", claim.source_url)
    # Losing its source means it can no longer be a fact, and an unsourced
    # statement cannot be strong evidence.
    return claim.model_copy(
        update={
            "source_url": None,
            "source_title": None,
            "published_date": None,
            "kind": ClaimKind.ESTIMATE,
            "evidence_strength": EvidenceStrength.WEAK,
            "confidence": min(claim.confidence, 0.3),
        }
    )


def score_run(outputs: dict[str, Any], ledger: EvidenceLedger) -> OpportunityScore:
    """Compute the final score. The only place a score is ever produced."""
    critic = outputs.get("critic")

    ratings = collect_ratings(
        outputs.get("market"), outputs.get("competitors"), outputs.get("personas"),
        outputs.get("financials"),
    )
    if critic is not None:
        ratings = apply_critic_overrides(ratings, critic.rating_overrides)

    return compute_score(
        ratings,
        ledger,
        contradictions=len(critic.contradictions) if critic else 0,
        unsound_categories=critic.unsound_categories if critic else (),
    )


class RunExecutor:
    """Executes one validation run end to end."""

    def __init__(self, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]):
        self._settings = settings
        self._sessionmaker = sessionmaker

    async def __call__(self, run_id: UUID, recorder: Any) -> None:
        submission = await self._load_submission(run_id)

        budget = RunBudget(
            max_per_agent=self._settings.max_searches_per_agent,
            max_per_run=self._settings.max_searches_per_run,
        )
        sources: dict[str, list[SourceRef]] = {}
        workflow = build_pipeline(self._settings, budget, sources)

        await recorder.emit("run", "started", {"stages": [s for s, _ in PROGRESS_STAGES]})

        outputs = await self._drive(workflow, submission, recorder, run_id)

        ledger, fabricated = build_ledger(
            [outputs.get(k) for k in ("market", "competitors", "personas") if outputs.get(k)],
            sources,
        )
        if fabricated:
            await recorder.emit(
                "evidence", "attribution_failed",
                {"count": len(fabricated), "urls": fabricated[:10]},
            )

        score = score_run(outputs, ledger)
        await recorder.emit("scoring", "completed", {"total": score.total, "band": score.band})

        await self._persist(run_id, outputs.get("report"), score, ledger, budget)

    async def _drive(
        self, workflow: Any, submission: IdeaSubmission, recorder: Any, run_id: UUID
    ) -> dict:
        """Run the graph, emitting progress as nodes transition."""
        runner = InMemoryRunner(agent=workflow, app_name=APP_NAME)

        # The session must exist before run_async; the runner does not create
        # one implicitly.
        user_id = "system"
        session_id = str(run_id)
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

        outputs: dict[str, Any] = {}
        seen: set[str] = set()

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=submission.model_dump_json(indent=2))],
            ),
        ):
            node = getattr(getattr(event, "node_info", None), "node_name", None) or event.author
            if node and node not in seen:
                seen.add(node)
                await recorder.emit(node, "started")

            output = getattr(event, "output", None)
            if output is not None:
                key = _OUTPUT_KEYS.get(node)
                if key:
                    outputs[key] = output
                    await recorder.emit(node, "completed")

        return outputs

    async def _load_submission(self, run_id: UUID) -> IdeaSubmission:
        async with self._sessionmaker() as session:
            row = await session.execute(select(Run.submission).where(Run.id == run_id))
            payload = row.scalar_one()
        return IdeaSubmission.model_validate(payload)

    async def _persist(
        self,
        run_id: UUID,
        report: Any,
        score: OpportunityScore,
        ledger: EvidenceLedger,
        budget: RunBudget,
    ) -> None:
        from app.reporting.markdown import render_markdown

        async with self._sessionmaker() as session:
            for claim in ledger.claims:
                session.add(
                    Evidence(
                        run_id=run_id,
                        claim=claim.model_dump(mode="json"),
                        source_url=claim.source_url,
                        attribution_verified=claim.source_url is not None,
                    )
                )

            content = report.model_dump(mode="json") if report is not None else {}
            session.add(
                Report(
                    run_id=run_id,
                    content=content,
                    score=score.model_dump(mode="json"),
                    markdown=render_markdown(report, score, ledger),
                )
            )
            await session.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(
                    score_total=score.total,
                    score_band=score.band,
                    usage=budget.snapshot(),
                )
            )
            await session.commit()


_OUTPUT_KEYS = {
    "manager": "hypothesis",
    "market_extract": "market",
    "competitor_extract": "competitors",
    "persona_extract": "personas",
    "financial": "financials",
    "critic": "critic",
    "reporter": "report",
}
