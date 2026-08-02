"""End-to-end scoring and rendering against fixtures. No network.

Exercises the path that runs after the agents return: attribution
verification -> evidence ledger -> critic overrides -> deterministic score ->
markdown. The weak-idea case is the primary regression test for the whole
product premise.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.llm.grounding import SourceRef
from app.reporting.markdown import render_markdown, render_number
from app.schemas.contracts import (
    CompetitorSet,
    Contradiction,
    CriticVerdict,
    MarketFindings,
    PersonaSet,
)
from app.schemas.evidence import (
    Claim,
    ClaimKind,
    EvidenceStrength,
    Number,
    Provenance,
    ScoreCategory,
)
from app.scoring.scorer import CategoryRating
from app.worker.execute import build_ledger, collect_ratings, score_run

C = ScoreCategory
REAL_URL = "https://industryreport.example/2026-study"


def sourced_claim(text: str, url: str = REAL_URL, days: int = 60) -> Claim:
    return Claim(
        text=text,
        kind=ClaimKind.FACT,
        evidence_strength=EvidenceStrength.STRONG,
        confidence=0.9,
        source_url=url,
        source_title="Industry Study 2026",
        published_date=datetime.now(timezone.utc).date() - timedelta(days=days),
        supports=[C.PROBLEM_SEVERITY, C.DEMAND_EVIDENCE, C.MARKET_ATTRACTIVENESS],
    )


def rating(cat: ScoreCategory, value: float) -> CategoryRating:
    return CategoryRating(category=cat, rating=value, justification="agent reasoning")


def retrieved(*urls: str) -> dict[str, list[SourceRef]]:
    return {"market_search": [SourceRef(url=u, title="t", domain="d") for u in urls]}


# --- Attribution ----------------------------------------------------------


def test_verified_citation_survives_the_ledger():
    findings = MarketFindings(problem_evidence=[sourced_claim("People struggle with X")])
    ledger, fabricated = build_ledger([findings], retrieved(REAL_URL))

    assert not fabricated
    assert ledger.claims[0].source_url == REAL_URL
    assert ledger.claims[0].evidence_strength is EvidenceStrength.STRONG


def test_fabricated_citation_is_stripped_and_downgraded():
    """A model inventing a plausible URL must not gain credit for it."""
    findings = MarketFindings(
        problem_evidence=[sourced_claim("Invented stat", url="https://fake.example/study")]
    )
    ledger, fabricated = build_ledger([findings], retrieved(REAL_URL))

    assert fabricated == ["https://fake.example/study"]
    claim = ledger.claims[0]
    assert claim.source_url is None
    assert claim.kind is ClaimKind.ESTIMATE
    assert claim.evidence_strength is EvidenceStrength.WEAK
    assert claim.confidence <= 0.3


def test_fabricated_citations_lower_the_final_score():
    real = MarketFindings(
        problem_evidence=[sourced_claim(f"finding {i}") for i in range(6)],
        ratings=[rating(c, 0.9) for c in C],
    )
    fake = MarketFindings(
        problem_evidence=[
            sourced_claim(f"finding {i}", url=f"https://fake.example/{i}") for i in range(6)
        ],
        ratings=[rating(c, 0.9) for c in C],
    )

    real_ledger, _ = build_ledger([real], retrieved(REAL_URL))
    fake_ledger, _ = build_ledger([fake], retrieved(REAL_URL))

    honest = score_run({"market": real}, real_ledger)
    invented = score_run({"market": fake}, fake_ledger)
    assert invented.total < honest.total


# --- Rating collection ----------------------------------------------------


def test_conflicting_ratings_take_the_lower():
    """Disagreement between agents is itself evidence of weakness."""
    optimistic = MarketFindings(ratings=[rating(C.DEMAND_EVIDENCE, 0.9)])
    cautious = CompetitorSet(ratings=[rating(C.DEMAND_EVIDENCE, 0.2)])
    collected = collect_ratings(optimistic, cautious)
    assert len(collected) == 1
    assert collected[0].rating == 0.2


# --- The adversarial case -------------------------------------------------


def test_weak_idea_lands_in_the_bottom_band():
    """A water-reminder app for everyone, free: no paid demand, no moat.

    Agents are made maximally enthusiastic on purpose. If this ever scores
    above the bottom band, the scorer or the critic has stopped working and
    the product is actively misleading founders.
    """
    market = MarketFindings(
        problem_evidence=[
            Claim(
                text="A Reddit thread had 400 upvotes about forgetting to drink water",
                kind=ClaimKind.ESTIMATE,
                evidence_strength=EvidenceStrength.ANECDOTAL,
                confidence=0.4,
                source_url="https://reddit.example/thread",
                supports=[C.PROBLEM_SEVERITY, C.DEMAND_EVIDENCE],
            )
        ],
        ratings=[rating(c, 1.0) for c in C],
    )
    competitors = CompetitorSet(ratings=[rating(c, 1.0) for c in C])
    personas = PersonaSet(ratings=[rating(c, 1.0) for c in C])

    critic = CriticVerdict(
        summary="Upvotes are not evidence of willingness to pay.",
        contradictions=[
            Contradiction(description="Free product, but revenue is projected", severity="high")
        ],
        unsupported_claims=["No evidence anyone pays for hydration reminders"],
        unsound_categories=[C.DEMAND_EVIDENCE, C.BUSINESS_MODEL],
        rating_overrides=[rating(C.DEMAND_EVIDENCE, 0.05), rating(C.BUSINESS_MODEL, 0.1)],
        must_validate_manually=["Find ten people who have paid for a reminder app"],
        verdict="Insufficient evidence of a paying customer.",
    )

    ledger, _ = build_ledger(
        [market, competitors, personas], retrieved("https://reddit.example/thread")
    )
    score = score_run(
        {"market": market, "competitors": competitors, "personas": personas, "critic": critic},
        ledger,
    )

    assert score.band == "high_risk", f"weak idea scored {score.total} ({score.band})"
    assert score.total <= 39
    assert score.penalties


def test_strong_idea_is_not_punished_by_default():
    """The scorer must discriminate, not just score everything badly.

    Evidence spans every category here, as a complete run's would: the
    competitor branch backs differentiation, the persona branch backs
    acquisition, and so on. Supplying evidence for only some categories
    correctly caps the rest, which is tested separately.
    """
    evidence = [
        sourced_claim(f"solid finding {i}", url=f"https://real.example/{i}").model_copy(
            update={"supports": list(C)}
        )
        for i in range(8)
    ]
    market = MarketFindings(problem_evidence=evidence, ratings=[rating(c, 0.9) for c in C])

    ledger, fabricated = build_ledger(
        [market], retrieved(*[f"https://real.example/{i}" for i in range(8)])
    )
    assert not fabricated

    score = score_run({"market": market}, ledger)
    assert score.total >= 60, f"well-evidenced idea scored only {score.total}"


def test_evidence_in_only_some_categories_caps_the_score():
    """Researching the market well does not earn credit for execution risk.

    A run where only the market branch produced evidence must not score like a
    complete one, however confident every agent sounded.
    """
    partial = [
        sourced_claim(f"market finding {i}", url=f"https://real.example/{i}").model_copy(
            update={"supports": [C.PROBLEM_SEVERITY, C.DEMAND_EVIDENCE]}
        )
        for i in range(8)
    ]
    market = MarketFindings(problem_evidence=partial, ratings=[rating(c, 1.0) for c in C])
    ledger, _ = build_ledger(
        [market], retrieved(*[f"https://real.example/{i}" for i in range(8)])
    )
    score = score_run({"market": market}, ledger)

    by_cat = {c.category: c for c in score.categories}
    assert by_cat[C.DEMAND_EVIDENCE].effective_rating > 0.8
    assert by_cat[C.EXECUTION_FEASIBILITY].effective_rating <= 0.25
    assert score.total < 60


# --- Rendering ------------------------------------------------------------


def test_assumed_numbers_are_visibly_flagged():
    number = Number(
        label="Monthly price",
        value=20.0,
        unit="EUR",
        provenance=Provenance.ASSUMED,
        rationale="No pricing evidence found for this segment",
    )
    rendered = render_number(number)
    assert "ASSUMED" in rendered
    assert "you are being asked to accept" in rendered


def test_calculated_numbers_show_their_formula():
    number = Number(
        label="Break-even customers",
        value=50.0,
        unit="customers",
        provenance=Provenance.CALCULATED,
        formula="monthly_fixed_costs / (price - variable_cost)",
    )
    assert "formula" in render_number(number)


def test_report_renders_without_a_report_agent_output():
    """A partial run must still hand back its score and evidence."""
    market = MarketFindings(problem_evidence=[sourced_claim("a finding")])
    ledger, _ = build_ledger([market], retrieved(REAL_URL))
    output = render_markdown(None, score_run({"market": market}, ledger), ledger)

    assert "Opportunity score" in output
    assert "did not complete" in output


def test_empty_evidence_is_called_out_in_the_report():
    from app.schemas.evidence import EvidenceLedger

    output = render_markdown(None, score_run({}, EvidenceLedger()), EvidenceLedger())
    assert "No verifiable evidence" in output


def test_unsourced_claims_are_marked_in_the_source_list():
    from app.schemas.evidence import EvidenceLedger

    ledger = EvidenceLedger()
    ledger.add(
        Claim(
            text="An assumption we made",
            kind=ClaimKind.ASSUMPTION,
            evidence_strength=EvidenceStrength.WEAK,
            confidence=0.3,
            supports=[C.PROBLEM_SEVERITY],
        )
    )
    output = render_markdown(None, score_run({}, ledger), ledger)
    assert "no source" in output
    assert "treat as unverified" in output
