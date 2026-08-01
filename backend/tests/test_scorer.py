"""Scorer tests. Pure and offline -- no network, no API key, no fixtures.

The central property under test: an agent cannot talk the score up. Every
test that matters here feeds the scorer maximal proposed ratings and checks
that weak evidence still drags the result down.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.schemas.evidence import (
    Claim,
    ClaimKind,
    EvidenceLedger,
    EvidenceStrength,
    ScoreCategory,
)
from app.scoring.scorer import (
    CategoryRating,
    compute_score,
    evidence_coverage,
    staleness_multiplier,
)
from app.scoring.weights import STALENESS_MIN_MULTIPLIER, WEIGHTS

ALL_CATEGORIES = list(WEIGHTS)


def claim(
    strength: EvidenceStrength = EvidenceStrength.STRONG,
    supports: list[ScoreCategory] | None = None,
    age_days: int = 30,
    confidence: float = 1.0,
    kind: ClaimKind = ClaimKind.FACT,
    text: str = "Some evidential statement",
) -> Claim:
    return Claim(
        text=text,
        kind=kind,
        evidence_strength=strength,
        confidence=confidence,
        source_url="https://example.com/report",
        source_title="Example Report",
        published_date=date.today() - timedelta(days=age_days),
        supports=supports or ALL_CATEGORIES,
    )


def perfect_ratings() -> list[CategoryRating]:
    return [
        CategoryRating(category=c, rating=1.0, justification="agent is confident")
        for c in ALL_CATEGORIES
    ]


# --- Provenance validators ------------------------------------------------


def test_fact_without_source_is_rejected():
    with pytest.raises(ValueError, match="no source_url"):
        Claim(
            text="The market is worth $50B",
            kind=ClaimKind.FACT,
            evidence_strength=EvidenceStrength.MODERATE,
            confidence=0.9,
        )


def test_strong_evidence_requires_a_date():
    with pytest.raises(ValueError, match="published_date"):
        Claim(
            text="Demand is growing",
            kind=ClaimKind.FACT,
            evidence_strength=EvidenceStrength.STRONG,
            confidence=0.9,
            source_url="https://example.com",
        )


def test_assumption_cannot_carry_a_source():
    with pytest.raises(ValueError, match="cannot carry a source_url"):
        Claim(
            text="Users will pay EUR20",
            kind=ClaimKind.ASSUMPTION,
            evidence_strength=EvidenceStrength.WEAK,
            confidence=0.4,
            source_url="https://example.com",
        )


# --- Staleness ------------------------------------------------------------


def test_recent_evidence_keeps_full_weight():
    assert staleness_multiplier(claim(age_days=100)) == 1.0


def test_ancient_evidence_decays_to_the_floor():
    assert staleness_multiplier(claim(age_days=365 * 10)) == STALENESS_MIN_MULTIPLIER


def test_staleness_decays_monotonically():
    ages = [0, 200, 400, 700, 1000, 1500, 2000, 5000]
    values = [staleness_multiplier(claim(age_days=a)) for a in ages]
    assert values == sorted(values, reverse=True)


def test_undated_evidence_is_neither_trusted_nor_discarded():
    undated = Claim(
        text="An undated statistic",
        kind=ClaimKind.ESTIMATE,
        evidence_strength=EvidenceStrength.MODERATE,
        confidence=0.8,
        source_url="https://example.com",
        supports=ALL_CATEGORIES,
    )
    assert 0.0 < staleness_multiplier(undated) < 1.0


# --- Coverage -------------------------------------------------------------


def test_coverage_saturates_at_one():
    ledger_claims = [claim() for _ in range(20)]
    assert evidence_coverage(ledger_claims) == 1.0


def test_stacking_anecdotes_does_not_equal_strong_evidence():
    """The most common way an agent manufactures false confidence."""
    anecdotes = [claim(strength=EvidenceStrength.ANECDOTAL) for _ in range(5)]
    one_strong = [claim(strength=EvidenceStrength.STRONG)]
    assert evidence_coverage(anecdotes) < evidence_coverage(one_strong)


# --- The core adversarial properties --------------------------------------


def test_no_evidence_cannot_score_well():
    """The primary regression test for the product's premise.

    A maximally enthusiastic set of agent ratings, with zero supporting
    evidence, must land in the bottom band.
    """
    result = compute_score(perfect_ratings(), EvidenceLedger())
    assert result.band == "high_risk"
    assert result.total <= 39, f"unsupported idea scored {result.total}"


def test_anecdotal_evidence_cannot_reach_the_top_band():
    ledger = EvidenceLedger()
    for i in range(30):
        ledger.add(claim(strength=EvidenceStrength.ANECDOTAL, text=f"anecdote {i}"))
    result = compute_score(perfect_ratings(), ledger)
    assert result.band in {"high_risk", "weak"}
    assert result.total < 60


def test_strong_fresh_evidence_permits_a_high_score():
    """The scorer must not be uniformly punitive, or it says nothing."""
    ledger = EvidenceLedger()
    for i in range(8):
        ledger.add(claim(strength=EvidenceStrength.STRONG, text=f"finding {i}"))
    result = compute_score(perfect_ratings(), ledger)
    assert result.total >= 80
    assert result.band == "strong"


def test_stale_strong_evidence_scores_below_fresh_strong_evidence():
    fresh, stale = EvidenceLedger(), EvidenceLedger()
    for i in range(8):
        fresh.add(claim(age_days=30, text=f"f{i}"))
        stale.add(claim(age_days=365 * 6, text=f"s{i}"))
    assert compute_score(perfect_ratings(), stale).total < compute_score(
        perfect_ratings(), fresh
    ).total


def test_contradictions_reduce_the_score():
    ledger = EvidenceLedger()
    for i in range(8):
        ledger.add(claim(text=f"finding {i}"))
    clean = compute_score(perfect_ratings(), ledger)
    contested = compute_score(perfect_ratings(), ledger, contradictions=3)
    assert contested.total < clean.total
    assert contested.penalties


def test_contradiction_penalty_is_capped():
    ledger = EvidenceLedger()
    for i in range(8):
        ledger.add(claim(text=f"finding {i}"))
    many = compute_score(perfect_ratings(), ledger, contradictions=99)
    assert many.penalty_points <= 20.0


def test_missing_category_scores_zero_not_skipped():
    """Agent silence is missing evidence, and missing evidence is not neutral."""
    ledger = EvidenceLedger()
    for i in range(8):
        ledger.add(claim(text=f"finding {i}"))
    partial = [r for r in perfect_ratings() if r.category is not ScoreCategory.DEMAND_EVIDENCE]
    result = compute_score(partial, ledger)
    demand = next(c for c in result.categories if c.category is ScoreCategory.DEMAND_EVIDENCE)
    assert demand.points == 0.0
    assert len(result.categories) == len(WEIGHTS)


def test_evidence_for_one_category_does_not_support_another():
    """Cross-contamination would let one good source inflate everything."""
    ledger = EvidenceLedger()
    for i in range(8):
        ledger.add(claim(supports=[ScoreCategory.MARKET_ATTRACTIVENESS], text=f"m{i}"))
    result = compute_score(perfect_ratings(), ledger)
    market = next(
        c for c in result.categories if c.category is ScoreCategory.MARKET_ATTRACTIVENESS
    )
    problem = next(
        c for c in result.categories if c.category is ScoreCategory.PROBLEM_SEVERITY
    )
    assert market.effective_rating > problem.effective_rating
    assert problem.supporting_claims == 0


def test_score_is_bounded_and_deterministic():
    ledger = EvidenceLedger()
    for i in range(12):
        ledger.add(claim(text=f"finding {i}"))
    runs = [compute_score(perfect_ratings(), ledger).total for _ in range(5)]
    assert len(set(runs)) == 1, "scorer must be deterministic"
    assert 0.0 <= runs[0] <= 100.0


def test_zero_ratings_with_strong_evidence_still_score_zero():
    """Evidence alone is not merit -- the agents must still rate the idea."""
    ledger = EvidenceLedger()
    for i in range(8):
        ledger.add(claim(text=f"finding {i}"))
    ratings = [
        CategoryRating(category=c, rating=0.0, justification="no merit found")
        for c in ALL_CATEGORIES
    ]
    assert compute_score(ratings, ledger).total == 0.0


def test_every_category_records_an_audit_trail():
    result = compute_score(perfect_ratings(), EvidenceLedger())
    for category in result.categories:
        assert category.adjustments, f"{category.category} capped silently"


def test_adjustments_only_ever_lower_a_rating():
    """Structural guarantee: no adjustment path can raise a proposed rating."""
    ledger = EvidenceLedger()
    for i in range(10):
        ledger.add(claim(strength=EvidenceStrength.STRONG, text=f"c{i}"))
    for proposed in [0.0, 0.25, 0.5, 0.75, 1.0]:
        ratings = [
            CategoryRating(category=c, rating=proposed, justification="x")
            for c in ALL_CATEGORIES
        ]
        for cat in compute_score(ratings, ledger).categories:
            assert cat.effective_rating <= cat.proposed_rating + 1e-9
