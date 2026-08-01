"""Scoring constants, isolated so they can be tuned without touching logic."""

from __future__ import annotations

from app.schemas.evidence import EvidenceStrength, ScoreCategory

# Category weights, summing to 100.
WEIGHTS: dict[ScoreCategory, int] = {
    ScoreCategory.PROBLEM_SEVERITY: 20,
    ScoreCategory.DEMAND_EVIDENCE: 20,
    ScoreCategory.MARKET_ATTRACTIVENESS: 15,
    ScoreCategory.DIFFERENTIATION: 15,
    ScoreCategory.BUSINESS_MODEL: 10,
    ScoreCategory.ACQUISITION_FEASIBILITY: 10,
    ScoreCategory.EXECUTION_FEASIBILITY: 10,
}

assert sum(WEIGHTS.values()) == 100, "Category weights must sum to 100"

# How much a single claim of each strength counts toward evidence coverage.
STRENGTH_VALUE: dict[EvidenceStrength, float] = {
    EvidenceStrength.STRONG: 1.0,
    EvidenceStrength.MODERATE: 0.6,
    EvidenceStrength.WEAK: 0.25,
    EvidenceStrength.ANECDOTAL: 0.1,
}

# Ceilings on a category's normalised rating, by the best evidence backing it.
# A category with nothing but anecdotes cannot score highly no matter how
# confident the agent sounded.
EVIDENCE_CEILING: dict[EvidenceStrength | None, float] = {
    EvidenceStrength.STRONG: 1.00,
    EvidenceStrength.MODERATE: 0.80,
    EvidenceStrength.WEAK: 0.50,
    EvidenceStrength.ANECDOTAL: 0.35,
    None: 0.25,  # no supporting evidence at all
}

# Evidence older than this starts losing weight; fully decayed at FLOOR.
STALENESS_FRESH_DAYS = 365
STALENESS_FLOOR_DAYS = 365 * 4
STALENESS_MIN_MULTIPLIER = 0.35

# Undated evidence is treated as neither fresh nor worthless.
UNDATED_MULTIPLIER = 0.6

# Coverage saturates, so decaying per-claim weight alone lets a pile of stale
# sources score like fresh ones. The freshness of the *best* supporting source
# therefore also scales the category ceiling. This floor bounds how far that
# can pull a rating down: stale evidence is devalued, not disqualified.
FRESHNESS_CEILING_FLOOR = 0.5

# Flat penalty per unresolved contradiction the critic found, in final points.
CONTRADICTION_PENALTY = 4.0
MAX_CONTRADICTION_PENALTY = 20.0

# Penalty in final points when the critic judges a category's reasoning unsound.
UNSOUND_CATEGORY_PENALTY = 3.0

BANDS: list[tuple[int, int, str, str]] = [
    (80, 100, "strong", "Strong opportunity - begin customer validation"),
    (60, 79, "promising", "Promising, but major assumptions need testing"),
    (40, 59, "weak", "Weak or insufficient evidence"),
    (0, 39, "high_risk", "High-risk opportunity or unclear problem"),
]

DISCLAIMER = (
    "This score measures the strength of the evidence gathered, not the "
    "likelihood of success. A high score means the idea survived scrutiny "
    "so far; it is not a prediction and does not substitute for talking to "
    "real customers."
)
