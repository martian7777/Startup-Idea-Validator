"""Grounding metadata -> evidence, and search accounting.

Two jobs, both hung off ADK's `after_model_callback` so they observe every
grounded call without agents having to cooperate:

  1. Harvest the real source list from `grounding_metadata`. The URLs an agent
     *writes* in its prose are model output and can be hallucinated; the URLs
     in grounding metadata are what the search tool actually retrieved. Only
     the latter are trusted as attribution.
  2. Charge the run's search budget using `web_search_queries`, which is the
     count Google actually bills for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.llm.budget import RunBudget


@dataclass(frozen=True)
class SourceRef:
    """A source the search tool genuinely retrieved."""

    url: str
    title: str | None = None
    domain: str | None = None


def extract_sources(grounding_metadata: Any) -> list[SourceRef]:
    """Pull retrieved web sources out of grounding metadata, de-duplicated."""
    if grounding_metadata is None:
        return []
    chunks = getattr(grounding_metadata, "grounding_chunks", None) or []

    seen: set[str] = set()
    sources: list[SourceRef] = []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web is None:
            continue
        uri = getattr(web, "uri", None)
        if not uri or uri in seen:
            continue
        seen.add(uri)
        sources.append(
            SourceRef(
                url=uri,
                title=getattr(web, "title", None),
                domain=getattr(web, "domain", None),
            )
        )
    return sources


def count_searches(grounding_metadata: Any) -> int:
    """Number of billable search queries the model chose to execute."""
    if grounding_metadata is None:
        return 0
    queries = getattr(grounding_metadata, "web_search_queries", None) or []
    return len(queries)


def make_grounding_callback(
    agent_name: str,
    budget: RunBudget,
    sink: dict[str, list[SourceRef]],
) -> Callable[..., None]:
    """Build an ADK `after_model_callback` that meters and harvests.

    Returns None so the response passes through untouched -- this observes,
    it does not rewrite model output.
    """

    def _after_model(callback_context: Any, llm_response: Any) -> None:
        metadata = getattr(llm_response, "grounding_metadata", None)

        usage = getattr(llm_response, "usage_metadata", None)
        if usage is not None:
            budget.charge_tokens(
                getattr(usage, "prompt_token_count", 0) or 0,
                getattr(usage, "candidates_token_count", 0) or 0,
            )

        if metadata is None:
            return None

        sources = extract_sources(metadata)
        if sources:
            bucket = sink.setdefault(agent_name, [])
            known = {s.url for s in bucket}
            bucket.extend(s for s in sources if s.url not in known)

        # Charged last: raising here must not lose the sources already
        # harvested from this response.
        budget.charge_searches(agent_name, count_searches(metadata))
        return None

    return _after_model


def verify_attribution(
    claim_urls: list[str], retrieved: list[SourceRef]
) -> tuple[list[str], list[str]]:
    """Split claimed URLs into those actually retrieved and those invented.

    A model asked for sources will sometimes produce plausible-looking URLs it
    never visited. Anything not in the retrieved set is treated as fabricated
    and must not reach the founder as attribution.
    """
    retrieved_urls = {s.url for s in retrieved}

    def normalise(url: str) -> str:
        return url.rstrip("/").lower()

    normalised = {normalise(u) for u in retrieved_urls}
    verified = [u for u in claim_urls if normalise(u) in normalised]
    fabricated = [u for u in claim_urls if normalise(u) not in normalised]
    return verified, fabricated
