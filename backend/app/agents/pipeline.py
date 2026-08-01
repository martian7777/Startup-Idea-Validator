"""The six-agent validation graph.

Built on ADK 2.0's Workflow runtime rather than SequentialAgent/ParallelAgent
composition, because the graph gives three things this pipeline needs:
per-node retry and timeout, a real JoinNode barrier for the research fan-in,
and `rerun_on_resume` for regenerating a single section.

Each research branch is two nodes -- a grounded search node, then a cheap
extraction node. Splitting them is what lets the search node use tools freely
while the extract node holds a strict output schema, and it keeps structuring
work on the lite model. It also gives the attribution check a natural seam:
the extract node's claimed URLs are verified against what search actually
retrieved.
"""

from __future__ import annotations

from google.adk import Workflow
from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.workflow import START, JoinNode, RetryConfig

from app.agents import prompts
from app.config import Settings
from app.llm.budget import RunBudget
from app.llm.grounding import SourceRef, make_grounding_callback
from app.schemas.contracts import (
    CompetitorSet,
    CriticVerdict,
    FinancialScenarios,
    MarketFindings,
    OpportunityReport,
    PersonaSet,
    StartupHypothesis,
)

# Node names double as progress keys in the UI and as budget buckets.
NODE_MANAGER = "manager"
NODE_MARKET_SEARCH = "market_search"
NODE_MARKET_EXTRACT = "market_extract"
NODE_COMPETITOR_SEARCH = "competitor_search"
NODE_COMPETITOR_EXTRACT = "competitor_extract"
NODE_PERSONA_SEARCH = "persona_search"
NODE_PERSONA_EXTRACT = "persona_extract"
NODE_JOIN = "research_join"
NODE_FINANCIAL = "financial"
NODE_CRITIC = "critic"
NODE_REPORT = "reporter"

# Ordered for the progress UI. The three search branches run concurrently, so
# the UI shows them as a group rather than implying a sequence.
PROGRESS_STAGES: list[tuple[str, str]] = [
    (NODE_MANAGER, "Structuring the hypothesis"),
    (NODE_MARKET_SEARCH, "Researching the market"),
    (NODE_COMPETITOR_SEARCH, "Analysing competitors"),
    (NODE_PERSONA_SEARCH, "Building customer segments"),
    (NODE_FINANCIAL, "Modelling financial scenarios"),
    (NODE_CRITIC, "Challenging the findings"),
    (NODE_REPORT, "Assembling the report"),
]


def build_pipeline(
    settings: Settings,
    budget: RunBudget,
    source_sink: dict[str, list[SourceRef]],
) -> Workflow:
    """Assemble the validation graph.

    `source_sink` collects the URLs search genuinely retrieved, keyed by node
    name. Attribution is verified against it after the run, so a model that
    invents a citation cannot pass it off as a source.
    """
    retry = RetryConfig(
        max_attempts=settings.node_max_attempts,
        initial_delay=2.0,
        backoff_factor=2.0,
    )

    def search_agent(name: str, instruction: str) -> LlmAgent:
        """Grounded node: tools on, schema off, metered."""
        tools = [google_search] if settings.grounding_available else []
        return LlmAgent(
            name=name,
            model=settings.model_research,
            instruction=instruction,
            tools=tools,
            after_model_callback=make_grounding_callback(name, budget, source_sink),
            retry_config=retry,
            timeout=settings.node_timeout_seconds,
        )

    def extract_agent(name: str, schema: type) -> LlmAgent:
        """Structuring node: schema on, tools off, cheapest model."""
        return LlmAgent(
            name=name,
            model=settings.model_extract,
            instruction=prompts.EXTRACT,
            output_schema=schema,
            retry_config=retry,
            timeout=settings.node_timeout_seconds,
        )

    manager = LlmAgent(
        name=NODE_MANAGER,
        model=settings.model_research,
        instruction=prompts.MANAGER,
        output_schema=StartupHypothesis,
        retry_config=retry,
        timeout=settings.node_timeout_seconds,
    )

    market_search = search_agent(NODE_MARKET_SEARCH, prompts.MARKET_SEARCH)
    market_extract = extract_agent(NODE_MARKET_EXTRACT, MarketFindings)
    competitor_search = search_agent(NODE_COMPETITOR_SEARCH, prompts.COMPETITOR_SEARCH)
    competitor_extract = extract_agent(NODE_COMPETITOR_EXTRACT, CompetitorSet)
    persona_search = search_agent(NODE_PERSONA_SEARCH, prompts.PERSONA_SEARCH)
    persona_extract = extract_agent(NODE_PERSONA_EXTRACT, PersonaSet)

    # Barrier: nothing downstream reads the merged ledger until all three
    # branches have landed. Merging happens after the join precisely because
    # concurrent writes to a shared ledger would race.
    join = JoinNode(name=NODE_JOIN)

    financial = LlmAgent(
        name=NODE_FINANCIAL,
        model=settings.model_research,
        instruction=prompts.FINANCIAL,
        output_schema=FinancialScenarios,
        retry_config=retry,
        timeout=settings.node_timeout_seconds,
    )
    critic = LlmAgent(
        name=NODE_CRITIC,
        model=settings.model_critic,
        instruction=prompts.CRITIC,
        output_schema=CriticVerdict,
        retry_config=retry,
        timeout=settings.node_timeout_seconds,
    )
    reporter = LlmAgent(
        name=NODE_REPORT,
        model=settings.model_critic,
        instruction=prompts.REPORT,
        output_schema=OpportunityReport,
        retry_config=retry,
        timeout=settings.node_timeout_seconds,
    )

    return Workflow(
        name="startup_validator",
        max_concurrency=3,
        edges=[
            (START, manager),
            (manager, market_search, market_extract, join),
            (manager, competitor_search, competitor_extract, join),
            (manager, persona_search, persona_extract, join),
            (join, financial, critic, reporter),
        ],
    )
