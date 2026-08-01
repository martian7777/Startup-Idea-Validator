"""Grounding harvest, search metering, and fabricated-URL detection.

Uses lightweight stand-ins shaped like `google.genai.types.GroundingMetadata`
so these run offline with no API key.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.llm.budget import RunBudget, SearchBudgetExceeded
from app.llm.grounding import (
    count_searches,
    extract_sources,
    make_grounding_callback,
    verify_attribution,
)


def web_chunk(uri: str, title: str = "T", domain: str = "d.com"):
    return SimpleNamespace(web=SimpleNamespace(uri=uri, title=title, domain=domain))


def metadata(uris: list[str], queries: list[str] | None = None):
    return SimpleNamespace(
        grounding_chunks=[web_chunk(u) for u in uris],
        web_search_queries=queries if queries is not None else ["q"],
    )


def response(md, prompt_tokens: int = 100, output_tokens: int = 50):
    return SimpleNamespace(
        grounding_metadata=md,
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens, candidates_token_count=output_tokens
        ),
    )


def test_extract_sources_dedupes():
    md = metadata(["https://a.com/1", "https://a.com/1", "https://b.com/2"])
    assert [s.url for s in extract_sources(md)] == ["https://a.com/1", "https://b.com/2"]


def test_extract_sources_handles_missing_metadata():
    assert extract_sources(None) == []
    assert extract_sources(SimpleNamespace(grounding_chunks=None)) == []


def test_count_searches_counts_executed_queries():
    assert count_searches(metadata([], ["a", "b", "c"])) == 3
    assert count_searches(None) == 0


def test_callback_harvests_sources_and_charges_budget():
    budget = RunBudget(max_per_agent=10, max_per_run=100)
    sink: dict = {}
    cb = make_grounding_callback("market", budget, sink)

    cb(None, response(metadata(["https://a.com"], ["q1", "q2"])))

    assert [s.url for s in sink["market"]] == ["https://a.com"]
    assert budget.snapshot()["total_searches"] == 2
    assert budget.snapshot()["input_tokens"] == 100


def test_callback_accumulates_across_calls_without_duplicates():
    budget = RunBudget(max_per_agent=10, max_per_run=100)
    sink: dict = {}
    cb = make_grounding_callback("market", budget, sink)

    cb(None, response(metadata(["https://a.com"])))
    cb(None, response(metadata(["https://a.com", "https://b.com"])))

    assert [s.url for s in sink["market"]] == ["https://a.com", "https://b.com"]


def test_budget_raises_when_agent_cap_exceeded():
    budget = RunBudget(max_per_agent=2, max_per_run=100)
    cb = make_grounding_callback("market", budget, {})
    with pytest.raises(SearchBudgetExceeded, match="over its cap"):
        cb(None, response(metadata(["https://a.com"], ["q1", "q2", "q3"])))


def test_budget_raises_when_run_cap_exceeded():
    budget = RunBudget(max_per_agent=100, max_per_run=3)
    cb = make_grounding_callback("market", budget, {})
    with pytest.raises(SearchBudgetExceeded, match="run cap"):
        cb(None, response(metadata(["https://a.com"], ["q"] * 4)))


def test_sources_survive_a_budget_overrun():
    """The overrun must not discard evidence already retrieved and paid for."""
    budget = RunBudget(max_per_agent=1, max_per_run=100)
    sink: dict = {}
    cb = make_grounding_callback("market", budget, sink)

    with pytest.raises(SearchBudgetExceeded):
        cb(None, response(metadata(["https://a.com", "https://b.com"], ["q1", "q2"])))

    assert len(sink["market"]) == 2


def test_budget_is_isolated_per_agent():
    budget = RunBudget(max_per_agent=2, max_per_run=100)
    market = make_grounding_callback("market", budget, {})
    comp = make_grounding_callback("competitor", budget, {})

    market(None, response(metadata([], ["q", "q"])))
    comp(None, response(metadata([], ["q", "q"])))  # must not trip market's cap

    assert budget.snapshot()["per_agent_searches"] == {"market": 2, "competitor": 2}


def test_check_before_refuses_once_exhausted():
    budget = RunBudget(max_per_agent=1, max_per_run=100)
    budget.charge_searches("market", 1)
    budget.check_before("competitor")  # unaffected
    with pytest.raises(SearchBudgetExceeded, match="exhausted"):
        budget.check_before("market")


# --- Fabricated attribution ----------------------------------------------


def test_fabricated_urls_are_detected():
    retrieved = extract_sources(metadata(["https://real.com/report"]))
    verified, fabricated = verify_attribution(
        ["https://real.com/report", "https://invented.com/study"], retrieved
    )
    assert verified == ["https://real.com/report"]
    assert fabricated == ["https://invented.com/study"]


def test_attribution_ignores_trailing_slash_and_case():
    retrieved = extract_sources(metadata(["https://Real.com/Report/"]))
    verified, fabricated = verify_attribution(["https://real.com/report"], retrieved)
    assert verified and not fabricated


def test_no_retrieved_sources_means_everything_is_fabricated():
    verified, fabricated = verify_attribution(["https://anything.com"], [])
    assert not verified
    assert fabricated == ["https://anything.com"]
