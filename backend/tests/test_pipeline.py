"""Graph-shape tests. No network -- assembly and wiring only.

These guard the structural decisions that are easy to break silently: the
research fan-out, the join barrier, model tiering, and the rule that a node
holding an output schema is never also the node doing the searching.
"""

from __future__ import annotations

from app.agents.pipeline import (
    NODE_CRITIC,
    NODE_JOIN,
    NODE_MANAGER,
    NODE_REPORT,
    build_pipeline,
)
from app.config import Settings
from app.llm.budget import RunBudget


def pipeline(**overrides):
    settings = Settings(gemini_api_key="test-key", **overrides)
    return build_pipeline(settings, RunBudget(max_per_agent=6, max_per_run=25), {})


def nodes_by_name(wf) -> dict:
    return {n.name: n for n in wf.graph.nodes}


def test_three_research_branches_converge_on_the_join():
    wf = pipeline()
    into_join = [e.from_node.name for e in wf.graph.edges if e.to_node.name == NODE_JOIN]
    assert len(into_join) == 3
    assert set(into_join) == {"market_extract", "competitor_extract", "persona_extract"}


def test_research_branches_start_from_the_manager():
    wf = pipeline()
    from_manager = {e.to_node.name for e in wf.graph.edges if e.from_node.name == NODE_MANAGER}
    assert from_manager == {"market_search", "competitor_search", "persona_search"}


def test_nothing_downstream_bypasses_the_join():
    """A shortcut past the barrier would read a half-built evidence ledger."""
    wf = pipeline()
    downstream = {"financial", NODE_CRITIC, NODE_REPORT}
    for edge in wf.graph.edges:
        if edge.to_node.name in downstream:
            assert edge.from_node.name in downstream | {NODE_JOIN}


def test_report_is_terminal():
    wf = pipeline()
    assert not [e for e in wf.graph.edges if e.from_node.name == NODE_REPORT]


def test_search_nodes_never_carry_an_output_schema():
    """The Search->Extract split is the whole reason grounding stays reliable."""
    for node in nodes_by_name(pipeline()).values():
        if node.name.endswith("_search"):
            assert getattr(node, "output_schema", None) is None
            assert getattr(node, "tools", [])


def test_extract_nodes_carry_a_schema_and_no_tools():
    for node in nodes_by_name(pipeline()).values():
        if node.name.endswith("_extract"):
            assert getattr(node, "output_schema", None) is not None
            assert not getattr(node, "tools", [])


def test_extraction_runs_on_the_cheap_model_and_judgement_on_the_best():
    settings = Settings(gemini_api_key="k")
    by_name = nodes_by_name(pipeline())
    assert by_name["market_extract"].model == settings.model_extract
    assert by_name["market_search"].model == settings.model_research
    assert by_name[NODE_CRITIC].model == settings.model_critic
    assert by_name[NODE_REPORT].model == settings.model_critic


def test_every_llm_node_has_retry_and_timeout():
    for node in nodes_by_name(pipeline()).values():
        if node.name in {"__START__", NODE_JOIN}:
            continue
        assert node.retry_config is not None, f"{node.name} has no retry policy"
        assert node.timeout, f"{node.name} has no timeout"


def test_disabling_grounding_removes_search_tools():
    """Fallback path for running without billing enabled."""
    wf = pipeline(enable_search_grounding=False)
    for node in nodes_by_name(wf).values():
        assert not getattr(node, "tools", [])


def test_concurrency_is_capped_to_the_research_fan_out():
    assert pipeline().max_concurrency == 3
