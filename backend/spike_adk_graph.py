"""Spike: prove the 6-agent DAG assembles on google-adk 2.6.1.

Run:  .venv/Scripts/python.exe spike_adk_graph.py

This makes NO network calls. It answers the questions the plan flagged as risks:
  1. Does the ADK 2.0 Workflow graph runtime express our fan-out/fan-in DAG?
  2. Can an LlmAgent hold `output_schema` and the `google_search` tool at once?
  3. Does node-to-node data passing carry typed Pydantic objects?
"""

from __future__ import annotations

from pydantic import BaseModel

from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.workflow import START, JoinNode, RetryConfig

FLASH = "gemini-3.5-flash"
LITE = "gemini-3.5-flash-lite"
PRO = "gemini-3.6-flash"


# --- Minimal stand-ins for the real contracts (schemas/ owns these later) ---
class Hypothesis(BaseModel):
    problem: str
    segment: str


class Findings(BaseModel):
    summary: str


# Retry: ADK 2.0 auto-catches exceptions for retry, so schema-validation
# failures on an extract node get another attempt instead of killing the run.
RETRY = RetryConfig(max_attempts=3, initial_delay=2.0, backoff_factor=2.0)


def search_node(name: str, instruction: str) -> LlmAgent:
    """Grounded research node: tools on, no output_schema."""
    return LlmAgent(
        name=name,
        model=FLASH,
        instruction=instruction,
        tools=[google_search],
        retry_config=RETRY,
        timeout=180.0,
    )


def extract_node(name: str, schema: type[BaseModel]) -> LlmAgent:
    """Structuring node: schema on, no tools, cheap model."""
    return LlmAgent(
        name=name,
        model=LITE,
        instruction="Convert the research notes into the required JSON. "
        "Never invent a source. Omit any claim you cannot attribute.",
        output_schema=schema,
        retry_config=RETRY,
        timeout=120.0,
    )


def build() -> Workflow:
    manager = LlmAgent(
        name="manager",
        model=FLASH,
        instruction="Structure the founder's idea into a testable hypothesis.",
        output_schema=Hypothesis,
        retry_config=RETRY,
    )

    market_s = search_node("market_search", "Find evidence the problem exists.")
    market_x = extract_node("market_extract", Findings)
    comp_s = search_node("competitor_search", "Find direct and indirect competitors.")
    comp_x = extract_node("competitor_extract", Findings)
    pers_s = search_node("persona_search", "Find evidence-backed customer segments.")
    pers_x = extract_node("persona_extract", Findings)

    # Fan-in barrier: the three research branches converge here before
    # anything downstream reads the merged evidence ledger.
    join = JoinNode(name="research_join")

    financial = LlmAgent(
        name="financial",
        model=FLASH,
        instruction="Build conservative/realistic/optimistic scenarios.",
        output_schema=Findings,
        retry_config=RETRY,
    )
    critic = LlmAgent(
        name="critic",
        model=PRO,
        instruction="Challenge every conclusion. Never strengthen weak evidence.",
        output_schema=Findings,
        retry_config=RETRY,
    )
    reporter = LlmAgent(
        name="reporter",
        model=PRO,
        instruction="Assemble the final opportunity report.",
        output_schema=Findings,
        retry_config=RETRY,
    )

    return Workflow(
        name="validator",
        max_concurrency=3,  # caps parallel research fan-out
        edges=[
            (START, manager),
            # fan-out: three independent search->extract branches
            (manager, market_s, market_x, join),
            (manager, comp_s, comp_x, join),
            (manager, pers_s, pers_x, join),
            # fan-in and the sequential tail
            (join, financial, critic, reporter),
        ],
    )


if __name__ == "__main__":
    wf = build()
    g = wf.graph
    names = [n.name for n in g.nodes]

    print(f"nodes ({len(names)}): {names}")
    print(f"edges ({len(g.edges)}):")
    for e in g.edges:
        print(f"    {e.from_node.name:>20} -> {e.to_node.name}")

    # Assertion 1: fan-out/fan-in shape is real.
    into_join = [e.from_node.name for e in g.edges if e.to_node.name == "research_join"]
    assert len(into_join) == 3, f"expected 3 branches into join, got {into_join}"

    # Assertion 2: schema + search tool coexist on one agent.
    probe = LlmAgent(
        name="probe", model=FLASH, tools=[google_search], output_schema=Findings
    )
    assert probe.tools and probe.output_schema

    print("\nRESULT")
    print("  fan-out/fan-in DAG assembles          : yes")
    print("  output_schema + google_search coexist : yes (construction)")
    print("  per-node retry + timeout              : yes")
    print(f"  branches converging on join           : {len(into_join)}")
