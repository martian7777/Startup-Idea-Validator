"""Deterministic opportunity scoring.

No LLM call happens anywhere in this module and none ever should. Agents
propose a 0-1 rating per category and supply evidence; this module decides
what that evidence is actually worth and does the arithmetic. Keeping the
maths here is what makes the score reproducible, auditable, and impossible
for a persuasive model to talk upward.

The scorer is adversarial by construction: every adjustment it applies can
only hold a rating down, never lift it.
"""

from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import (
    Claim,
    EvidenceLedger,
    EvidenceStrength,
    ScoreCategory,
)
from app.scoring.weights import (
    BANDS,
    CONTRADICTION_PENALTY,
    DISCLAIMER,
    EVIDENCE_CEILING,
    FRESHNESS_CEILING_FLOOR,
    MAX_CONTRADICTION_PENALTY,
    STALENESS_FLOOR_DAYS,
    STALENESS_FRESH_DAYS,
    STALENESS_MIN_MULTIPLIER,
    STRENGTH_VALUE,
    UNDATED_MULTIPLIER,
    UNSOUND_CATEGORY_PENALTY,
    WEIGHTS,
)


class CategoryRating(BaseModel):
    """An agent's proposed rating for one category.

    `rating` is a proposal, not a verdict -- the scorer may cap it.
    """

    model_config = ConfigDict(use_enum_values=False)

    category: ScoreCategory
    rating: float = Field(ge=0.0, le=1.0)
    justification: str = Field(min_length=1)


class CategoryScore(BaseModel):
    """The scorer's audit trail for a single category."""

    model_config = ConfigDict(use_enum_values=False)

    category: ScoreCategory
    weight: int
    proposed_rating: float
    effective_rating: float
    points: float
    max_points: int
    best_evidence: EvidenceStrength | None
    supporting_claims: int
    evidence_coverage: float
    adjustments: list[str] = Field(default_factory=list)


class OpportunityScore(BaseModel):
    """Final score with everything needed to reconstruct how it was reached."""

    total: float
    band: str
    band_label: str
    categories: list[CategoryScore]
    penalties: list[str] = Field(default_factory=list)
    penalty_points: float = 0.0
    disclaimer: str = DISCLAIMER


def staleness_multiplier(claim: Claim) -> float:
    """Weight decay for ageing evidence.

    Full weight for the first year, linear decay to a floor at four years.
    Undated evidence gets a fixed middling multiplier -- we cannot verify it
    is current, so we neither trust nor discard it.
    """
    age = claim.age_days
    if age is None:
        return UNDATED_MULTIPLIER
    if age <= STALENESS_FRESH_DAYS:
        return 1.0
    if age >= STALENESS_FLOOR_DAYS:
        return STALENESS_MIN_MULTIPLIER
    span = STALENESS_FLOOR_DAYS - STALENESS_FRESH_DAYS
    progress = (age - STALENESS_FRESH_DAYS) / span
    return 1.0 - progress * (1.0 - STALENESS_MIN_MULTIPLIER)


def evidence_coverage(claims: Iterable[Claim]) -> float:
    """Aggregate evidential support for a category, saturating at 1.0.

    Diminishing returns are deliberate: ten mediocre blog posts should not
    outweigh one solid industry study, and stacking weak citations is the
    most common way a research agent manufactures false confidence.
    """
    total = 0.0
    for claim in claims:
        base = STRENGTH_VALUE[claim.evidence_strength]
        total += base * staleness_multiplier(claim) * claim.confidence
    return min(1.0, total)


def _best_strength(claims: list[Claim]) -> EvidenceStrength | None:
    """Strongest evidence backing a category, ignoring badly stale items."""
    order = [
        EvidenceStrength.STRONG,
        EvidenceStrength.MODERATE,
        EvidenceStrength.WEAK,
        EvidenceStrength.ANECDOTAL,
    ]
    live = [c for c in claims if staleness_multiplier(c) > STALENESS_MIN_MULTIPLIER]
    pool = live or claims
    for strength in order:
        if any(c.evidence_strength is strength for c in pool):
            return strength
    return None


def score_category(
    rating: CategoryRating,
    ledger: EvidenceLedger,
    unsound: bool = False,
) -> CategoryScore:
    """Convert one proposed rating into earned points."""
    category = rating.category
    weight = WEIGHTS[category]
    claims = ledger.supporting(category)
    coverage = evidence_coverage(claims)
    best = _best_strength(claims)

    effective = rating.rating
    adjustments: list[str] = []

    # Freshness of the best available source scales the ceiling. Without this,
    # coverage saturation lets a stack of years-old reports look identical to
    # current ones -- the exact failure mode the critic is meant to catch.
    freshness = max((staleness_multiplier(c) for c in claims), default=1.0)
    freshness_factor = FRESHNESS_CEILING_FLOOR + (1 - FRESHNESS_CEILING_FLOOR) * freshness

    ceiling = EVIDENCE_CEILING[best] * freshness_factor
    if effective > ceiling:
        label = best.value if best else "no supporting evidence"
        detail = f"best evidence is {label}"
        if freshness_factor < 1.0:
            detail += f", freshest source scores {freshness:.2f} on recency"
        adjustments.append(
            f"Rating capped {effective:.2f} -> {ceiling:.2f}: {detail}."
        )
        effective = ceiling

    # Coverage gate: a lone qualifying citation should not carry a full score.
    if coverage < 1.0:
        gated = effective * (0.5 + 0.5 * coverage)
        if gated < effective:
            adjustments.append(
                f"Rating reduced {effective:.2f} -> {gated:.2f}: evidence coverage "
                f"{coverage:.2f} across {len(claims)} claim(s)."
            )
            effective = gated

    if unsound:
        adjustments.append("Critic judged the reasoning for this category unsound.")

    return CategoryScore(
        category=category,
        weight=weight,
        proposed_rating=rating.rating,
        effective_rating=round(effective, 4),
        points=round(effective * weight, 4),
        max_points=weight,
        best_evidence=best,
        supporting_claims=len(claims),
        evidence_coverage=round(coverage, 4),
        adjustments=adjustments,
    )


def band_for(total: float) -> tuple[str, str]:
    rounded = int(round(total))
    for low, high, key, label in BANDS:
        if low <= rounded <= high:
            return key, label
    return BANDS[-1][2], BANDS[-1][3]


def compute_score(
    ratings: list[CategoryRating],
    ledger: EvidenceLedger,
    contradictions: int = 0,
    unsound_categories: Iterable[ScoreCategory] = (),
) -> OpportunityScore:
    """Compute the final 0-100 opportunity score.

    A category with no rating scores zero rather than being skipped: silence
    from an agent is missing evidence, and missing evidence is not neutral.
    """
    unsound = set(unsound_categories)
    by_category = {r.category: r for r in ratings}

    categories: list[CategoryScore] = []
    for category in WEIGHTS:
        rating = by_category.get(category)
        if rating is None:
            rating = CategoryRating(
                category=category,
                rating=0.0,
                justification="No rating produced for this category.",
            )
        categories.append(score_category(rating, ledger, unsound=category in unsound))

    subtotal = sum(c.points for c in categories)

    penalties: list[str] = []
    penalty_points = 0.0

    if contradictions > 0:
        deduction = min(
            contradictions * CONTRADICTION_PENALTY, MAX_CONTRADICTION_PENALTY
        )
        penalty_points += deduction
        penalties.append(
            f"-{deduction:.1f} for {contradictions} unresolved contradiction(s) "
            "between agents."
        )

    if unsound:
        deduction = len(unsound) * UNSOUND_CATEGORY_PENALTY
        penalty_points += deduction
        names = ", ".join(sorted(c.value for c in unsound))
        penalties.append(f"-{deduction:.1f} for unsound reasoning in: {names}.")

    total = max(0.0, min(100.0, subtotal - penalty_points))
    band, band_label = band_for(total)

    return OpportunityScore(
        total=round(total, 2),
        band=band,
        band_label=band_label,
        categories=categories,
        penalties=penalties,
        penalty_points=round(penalty_points, 2),
    )
