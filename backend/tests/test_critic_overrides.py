"""The critic's influence must be one-directional.

If a sufficiently persuasive critic could raise a rating, the whole
"never flatter the founder" guarantee becomes advisory. These tests pin
that it cannot.
"""

from __future__ import annotations

from app.schemas.evidence import ScoreCategory
from app.scoring.scorer import CategoryRating, apply_critic_overrides

C = ScoreCategory


def rating(cat: ScoreCategory, value: float, why: str = "because") -> CategoryRating:
    return CategoryRating(category=cat, rating=value, justification=why)


def test_critic_can_lower_a_rating():
    merged = apply_critic_overrides(
        [rating(C.DEMAND_EVIDENCE, 0.9)],
        [rating(C.DEMAND_EVIDENCE, 0.3, "no evidence anyone pays")],
    )
    assert merged[0].rating == 0.3
    assert "Critic lowered this" in merged[0].justification


def test_critic_cannot_raise_a_rating():
    merged = apply_critic_overrides(
        [rating(C.DEMAND_EVIDENCE, 0.3)],
        [rating(C.DEMAND_EVIDENCE, 0.95, "actually this looks great")],
    )
    assert merged[0].rating == 0.3


def test_equal_override_does_not_rewrite_justification():
    merged = apply_critic_overrides(
        [rating(C.BUSINESS_MODEL, 0.5, "original reasoning")],
        [rating(C.BUSINESS_MODEL, 0.5, "critic agrees")],
    )
    assert merged[0].justification == "original reasoning"


def test_untouched_categories_pass_through():
    merged = apply_critic_overrides(
        [rating(C.PROBLEM_SEVERITY, 0.7), rating(C.EXECUTION_FEASIBILITY, 0.4)],
        [rating(C.PROBLEM_SEVERITY, 0.2)],
    )
    by_cat = {m.category: m.rating for m in merged}
    assert by_cat[C.PROBLEM_SEVERITY] == 0.2
    assert by_cat[C.EXECUTION_FEASIBILITY] == 0.4


def test_critic_cannot_introduce_an_unrated_category():
    """A category nobody researched stays unrated -- and so scores zero."""
    merged = apply_critic_overrides(
        [rating(C.PROBLEM_SEVERITY, 0.6)],
        [rating(C.MARKET_ATTRACTIVENESS, 0.9, "invented from nowhere")],
    )
    assert len(merged) == 1
    assert merged[0].category is C.PROBLEM_SEVERITY


def test_overrides_never_raise_across_the_full_grid():
    for original in [0.0, 0.2, 0.5, 0.8, 1.0]:
        for override in [0.0, 0.2, 0.5, 0.8, 1.0]:
            merged = apply_critic_overrides(
                [rating(C.DIFFERENTIATION, original)],
                [rating(C.DIFFERENTIATION, override)],
            )
            assert merged[0].rating <= original + 1e-9
