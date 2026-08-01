"""Per-agent input and output contracts.

Each agent is a prompt wrapped around one of these models, so this file is the
real specification of the pipeline. Two conventions run throughout:

  * Agents never emit a bare number -- they emit `Number`, which forces them
    to declare whether it was sourced, calculated, or assumed.
  * Agents never emit a bare assertion -- they emit `Claim`, which forces
    attribution before a statement can be called a fact.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import Claim, Number, ScoreCategory
from app.scoring.scorer import CategoryRating


class RevenueModel(str, Enum):
    SUBSCRIPTION = "subscription"
    ONE_TIME = "one_time"
    MARKETPLACE = "marketplace"
    ADVERTISING = "advertising"
    USAGE_BASED = "usage_based"
    FREEMIUM = "freemium"
    SERVICES = "services"
    OTHER = "other"


class IdeaSubmission(BaseModel):
    """What the founder submits."""

    idea: str = Field(min_length=20, max_length=4000)
    target_customer: str = Field(min_length=3, max_length=500)
    country: str = Field(min_length=2, max_length=100)
    industry: str = Field(min_length=2, max_length=100)
    revenue_model: RevenueModel = RevenueModel.SUBSCRIPTION
    monthly_budget_eur: float | None = Field(default=None, ge=0)
    founder_skills: str | None = Field(default=None, max_length=1000)


# --- Manager --------------------------------------------------------------


class StartupHypothesis(BaseModel):
    """The idea restated as something falsifiable."""

    problem_statement: str
    target_segment: str
    proposed_solution: str
    value_hypothesis: str
    riskiest_assumptions: list[str] = Field(min_length=1, max_length=8)
    research_questions: list[str] = Field(min_length=3, max_length=12)
    missing_information: list[str] = Field(default_factory=list)


# --- Research branches ----------------------------------------------------


class MarketFindings(BaseModel):
    problem_evidence: list[Claim] = Field(default_factory=list)
    demand_signals: list[Claim] = Field(default_factory=list)
    trends: list[Claim] = Field(default_factory=list)
    market_size_notes: str | None = None
    ratings: list[CategoryRating] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class Competitor(BaseModel):
    name: str
    target_user: str
    pricing: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunity: str | None = None
    source_url: str | None = None


class CompetitorSet(BaseModel):
    direct: list[Competitor] = Field(default_factory=list)
    indirect: list[Competitor] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    evidence: list[Claim] = Field(default_factory=list)
    ratings: list[CategoryRating] = Field(default_factory=list)


class Persona(BaseModel):
    name: str
    description: str
    jobs_to_be_done: list[str] = Field(default_factory=list)
    pains: list[str] = Field(default_factory=list)
    current_alternatives: list[str] = Field(default_factory=list)
    willingness_to_pay_hypothesis: str | None = None
    is_early_adopter: bool = False
    # Personas are hypotheses until a human talks to someone. The field is
    # required so the UI can never present one as confirmed by default.
    validation_status: str = "unconfirmed - requires customer interviews"


class PersonaSet(BaseModel):
    personas: list[Persona] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    evidence: list[Claim] = Field(default_factory=list)
    ratings: list[CategoryRating] = Field(default_factory=list)


# --- Financial ------------------------------------------------------------


class Scenario(BaseModel):
    name: str  # conservative | realistic | optimistic
    assumptions: list[Number] = Field(default_factory=list)
    monthly_revenue: Number
    monthly_costs: Number
    break_even_customers: Number
    notes: str | None = None


class FinancialScenarios(BaseModel):
    conservative: Scenario
    realistic: Scenario
    optimistic: Scenario
    pricing_rationale: str
    ratings: list[CategoryRating] = Field(default_factory=list)


# --- Critic ---------------------------------------------------------------


class Contradiction(BaseModel):
    description: str
    agents_involved: list[str] = Field(default_factory=list)
    severity: str = "moderate"


class CriticVerdict(BaseModel):
    """The critic may only lower confidence, never raise it.

    `rating_overrides` is applied by the scorer as a floor-taking operation:
    an override that is *higher* than the proposed rating is discarded.
    """

    model_config = ConfigDict(use_enum_values=False)

    summary: str
    contradictions: list[Contradiction] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    outdated_sources: list[str] = Field(default_factory=list)
    unsound_categories: list[ScoreCategory] = Field(default_factory=list)
    rating_overrides: list[CategoryRating] = Field(default_factory=list)
    must_validate_manually: list[str] = Field(min_length=1)
    verdict: str


# --- Report ---------------------------------------------------------------


class ValidationStep(BaseModel):
    day: int = Field(ge=1, le=7)
    action: str
    success_signal: str


class OpportunityReport(BaseModel):
    """The 16 sections of the final report.

    Score is absent by design -- it is attached by the deterministic scorer
    after this model is produced, so the report agent never sees a number it
    could rationalise toward.
    """

    executive_summary: str
    hypothesis: StartupHypothesis
    problem_analysis: str
    segments: PersonaSet
    market_evidence: MarketFindings
    competitors: CompetitorSet
    differentiation: list[str]
    revenue_model_analysis: str
    financials: FinancialScenarios
    key_assumptions: list[str]
    major_risks: list[str]
    critic_verdict: CriticVerdict
    validation_plan: list[ValidationStep] = Field(min_length=1, max_length=7)
    interview_questions: list[str] = Field(min_length=3)
