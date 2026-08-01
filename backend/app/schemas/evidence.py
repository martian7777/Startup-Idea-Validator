"""Evidence primitives.

These two types carry the product's core promise: nothing reaches the founder
without a traceable origin. `Claim` is the unit of external evidence; `Number`
is the unit of quantitative reasoning. Both make provenance a validation
concern rather than a prompt instruction, because a prompt is a request and a
validator is a guarantee.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    ANECDOTAL = "anecdotal"


class ClaimKind(str, Enum):
    FACT = "fact"
    ESTIMATE = "estimate"
    ASSUMPTION = "assumption"


class Provenance(str, Enum):
    SOURCED = "sourced"
    CALCULATED = "calculated"
    ASSUMED = "assumed"


class ScoreCategory(str, Enum):
    """The seven scoring dimensions. Weights live in scoring/weights.py."""

    PROBLEM_SEVERITY = "problem_severity"
    DEMAND_EVIDENCE = "demand_evidence"
    MARKET_ATTRACTIVENESS = "market_attractiveness"
    DIFFERENTIATION = "differentiation"
    BUSINESS_MODEL = "business_model"
    ACQUISITION_FEASIBILITY = "acquisition_feasibility"
    EXECUTION_FEASIBILITY = "execution_feasibility"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Claim(BaseModel):
    """A single evidential statement with its origin attached.

    A claim without a URL can still exist -- it is simply not a `fact`. The
    validator enforces that asymmetry so an agent cannot assert strong
    evidence while omitting the thing that would make it checkable.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=1)
    kind: ClaimKind
    evidence_strength: EvidenceStrength
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

    source_url: str | None = None
    source_title: str | None = None
    published_date: date | None = None
    retrieved_at: datetime = Field(default_factory=_utcnow)

    supports: list[ScoreCategory] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_attribution(self) -> "Claim":
        # A fact is a statement about the world; it must be checkable.
        if self.kind is ClaimKind.FACT and not self.source_url:
            raise ValueError(
                f"Claim marked 'fact' has no source_url: {self.text[:80]!r}. "
                "Downgrade it to 'estimate' or 'assumption', or attach a source."
            )
        # Strength is a claim about the evidence, not about the assertion.
        # Undated evidence cannot be called strong -- staleness is unknowable.
        if self.evidence_strength is EvidenceStrength.STRONG:
            if not self.source_url or not self.published_date:
                raise ValueError(
                    f"Claim marked 'strong' needs both source_url and "
                    f"published_date: {self.text[:80]!r}"
                )
        if self.kind is ClaimKind.ASSUMPTION and self.source_url:
            raise ValueError(
                "An assumption cannot carry a source_url -- if it has a source, "
                "it is a fact or an estimate."
            )
        return self

    @property
    def age_days(self) -> int | None:
        if self.published_date is None:
            return None
        return (_utcnow().date() - self.published_date).days


class Number(BaseModel):
    """A quantity whose derivation is always inspectable.

    Every number in a financial scenario is one of: taken from a source,
    computed from other numbers, or invented as an assumption. The founder
    must be able to tell which at a glance, so the distinction is structural.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    label: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    provenance: Provenance

    formula: str | None = None
    source_claim_id: UUID | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _enforce_provenance(self) -> "Number":
        if self.provenance is Provenance.SOURCED and self.source_claim_id is None:
            raise ValueError(
                f"Number {self.label!r} claims to be 'sourced' but cites no claim."
            )
        if self.provenance is Provenance.CALCULATED and not self.formula:
            raise ValueError(
                f"Number {self.label!r} claims to be 'calculated' but shows no formula."
            )
        if self.provenance is Provenance.ASSUMED:
            if self.source_claim_id is not None:
                raise ValueError(
                    f"Number {self.label!r} is 'assumed' but cites a claim -- "
                    "mark it 'sourced' instead."
                )
            if not self.rationale:
                raise ValueError(
                    f"Assumed number {self.label!r} must state a rationale so the "
                    "founder knows what they are being asked to accept."
                )
        return self


class EvidenceLedger(BaseModel):
    """Run-scoped collection of claims, deduplicated by source URL.

    Merged after the research branches join. Deliberately not written to
    concurrently -- parallel nodes each own a private output key.
    """

    claims: list[Claim] = Field(default_factory=list)

    def add(self, claim: Claim) -> None:
        if claim.source_url:
            for existing in self.claims:
                if existing.source_url == claim.source_url and existing.text == claim.text:
                    return
        self.claims.append(claim)

    def merge(self, other: "EvidenceLedger") -> None:
        for claim in other.claims:
            self.add(claim)

    def by_id(self, claim_id: UUID) -> Claim | None:
        return next((c for c in self.claims if c.id == claim_id), None)

    def supporting(self, category: ScoreCategory) -> list[Claim]:
        return [c for c in self.claims if category in c.supports]
