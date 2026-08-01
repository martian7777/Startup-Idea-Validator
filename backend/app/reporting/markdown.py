"""Renders the downloadable report.

The rendering rule throughout: never let an assumption read like a fact. Every
number shows its provenance inline and every claim shows its source and date,
because the founder is going to skim this and act on whatever looks solid.
"""

from __future__ import annotations

from typing import Any

from app.schemas.evidence import Claim, EvidenceLedger, Number, Provenance
from app.scoring.scorer import OpportunityScore

PROVENANCE_MARK = {
    Provenance.SOURCED: "sourced",
    Provenance.CALCULATED: "calculated",
    Provenance.ASSUMED: "ASSUMED",
}


def render_number(number: Number) -> str:
    mark = PROVENANCE_MARK[number.provenance]
    line = f"**{number.label}**: {number.value:,.2f} {number.unit} _({mark})_"
    if number.provenance is Provenance.CALCULATED and number.formula:
        line += f"\n    - formula: `{number.formula}`"
    if number.provenance is Provenance.ASSUMED and number.rationale:
        line += f"\n    - you are being asked to accept: {number.rationale}"
    return line


def render_claim(claim: Claim) -> str:
    bits = [f"- {claim.text}"]
    if claim.source_url:
        title = claim.source_title or claim.source_url
        bits.append(f"  - source: [{title}]({claim.source_url})")
    else:
        bits.append("  - **no source** - treat as unverified")
    if claim.published_date:
        age = claim.age_days
        stale = " (dated - verify before relying on it)" if age and age > 365 * 3 else ""
        bits.append(f"  - published: {claim.published_date.isoformat()}{stale}")
    bits.append(
        f"  - {claim.kind.value} / {claim.evidence_strength.value} / "
        f"confidence {claim.confidence:.0%}"
    )
    return "\n".join(bits)


def render_score(score: OpportunityScore) -> str:
    lines = [
        "## Opportunity score",
        "",
        f"### {score.total:.0f} / 100 - {score.band_label}",
        "",
        f"> {score.disclaimer}",
        "",
        "| Category | Proposed | Effective | Points | Max | Evidence |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for category in score.categories:
        best = category.best_evidence.value if category.best_evidence else "none"
        lines.append(
            f"| {category.category.value.replace('_', ' ')} "
            f"| {category.proposed_rating:.2f} | {category.effective_rating:.2f} "
            f"| {category.points:.1f} | {category.max_points} "
            f"| {best} ({category.supporting_claims}) |"
        )

    adjustments = [
        f"- **{c.category.value.replace('_', ' ')}**: {a}"
        for c in score.categories
        for a in c.adjustments
    ]
    if adjustments:
        lines += ["", "### Why the score was held down", ""] + adjustments
    if score.penalties:
        lines += ["", "### Penalties applied", ""] + [f"- {p}" for p in score.penalties]
    return "\n".join(lines)


def _section(title: str, body: Any) -> list[str]:
    if not body:
        return [f"## {title}", "", "_Not produced for this run._", ""]
    if isinstance(body, str):
        return [f"## {title}", "", body, ""]
    if isinstance(body, list):
        return [f"## {title}", ""] + [f"- {item}" for item in body] + [""]
    return [f"## {title}", "", str(body), ""]


def render_markdown(
    report: Any, score: OpportunityScore, ledger: EvidenceLedger
) -> str:
    """Render the full report. Tolerates a missing report so a partially
    completed run still yields its score and evidence."""
    lines: list[str] = ["# Startup Opportunity Report", ""]

    if report is None:
        lines += [
            (
                "_The report agent did not complete. The score and evidence below "
                "reflect what was gathered before the run stopped._"
            ),
            "",
        ]
        lines += [render_score(score), ""]
    else:
        lines += _section("Executive summary", report.executive_summary)
        lines += [render_score(score), ""]

        hypothesis = report.hypothesis
        lines += ["## Startup hypothesis", ""]
        lines += [
            f"**Problem**: {hypothesis.problem_statement}",
            "",
            f"**Segment**: {hypothesis.target_segment}",
            "",
            f"**Solution**: {hypothesis.proposed_solution}",
            "",
            f"**Value hypothesis**: {hypothesis.value_hypothesis}",
            "",
            "**Riskiest assumptions**:",
            "",
        ]
        lines += [f"- {a}" for a in hypothesis.riskiest_assumptions] + [""]

        lines += _section("Problem analysis", report.problem_analysis)

        lines += ["## Target customer segments", ""]
        for persona in report.segments.personas:
            lines += [
                f"### {persona.name}",
                "",
                persona.description,
                "",
                f"- **Validation status**: {persona.validation_status}",
            ]
            if persona.jobs_to_be_done:
                lines.append(f"- **Jobs**: {'; '.join(persona.jobs_to_be_done)}")
            if persona.pains:
                lines.append(f"- **Pains**: {'; '.join(persona.pains)}")
            if persona.current_alternatives:
                lines.append(f"- **Uses today**: {'; '.join(persona.current_alternatives)}")
            if persona.willingness_to_pay_hypothesis:
                lines.append(
                    f"- **Willingness to pay (hypothesis)**: "
                    f"{persona.willingness_to_pay_hypothesis}"
                )
            lines.append("")

        lines += ["## Competitor comparison", ""]
        competitors = list(report.competitors.direct) + list(report.competitors.indirect)
        if competitors:
            lines += [
                "| Competitor | Target user | Pricing | Strength | Weakness | Opportunity |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
            for c in competitors:
                lines.append(
                    f"| {c.name} | {c.target_user} | {c.pricing or '-'} "
                    f"| {'; '.join(c.strengths) or '-'} | {'; '.join(c.weaknesses) or '-'} "
                    f"| {c.opportunity or '-'} |"
                )
        else:
            lines.append("_No competitors identified - treat this as a warning sign._")
        lines.append("")

        lines += _section("Differentiation opportunities", report.differentiation)
        lines += _section("Revenue-model analysis", report.revenue_model_analysis)

        lines += ["## Financial scenarios", ""]
        for scenario in (
            report.financials.conservative,
            report.financials.realistic,
            report.financials.optimistic,
        ):
            lines += [f"### {scenario.name.title()}", ""]
            for number in (
                scenario.monthly_revenue,
                scenario.monthly_costs,
                scenario.break_even_customers,
            ):
                lines.append(f"- {render_number(number)}")
            for assumption in scenario.assumptions:
                lines.append(f"- {render_number(assumption)}")
            if scenario.notes:
                lines += ["", scenario.notes]
            lines.append("")

        lines += _section("Key assumptions", report.key_assumptions)
        lines += _section("Major risks", report.major_risks)

        critic = report.critic_verdict
        lines += ["## Critic's verdict", "", critic.summary, "", f"**{critic.verdict}**", ""]
        if critic.contradictions:
            lines += ["### Contradictions found", ""]
            lines += [f"- {c.description} ({c.severity})" for c in critic.contradictions]
            lines.append("")
        if critic.unsupported_claims:
            lines += ["### Unsupported claims", ""]
            lines += [f"- {c}" for c in critic.unsupported_claims] + [""]
        if critic.outdated_sources:
            lines += ["### Outdated sources", ""]
            lines += [f"- {s}" for s in critic.outdated_sources] + [""]
        lines += ["### You must validate these yourself", ""]
        lines += [f"- {item}" for item in critic.must_validate_manually] + [""]

        lines += ["## Seven-day validation plan", ""]
        for step in sorted(report.validation_plan, key=lambda s: s.day):
            lines += [
                f"**Day {step.day}**: {step.action}",
                f"  - success signal: {step.success_signal}",
                "",
            ]

        lines += _section("Customer interview questions", report.interview_questions)

    lines += ["## Sources and confidence", ""]
    if ledger.claims:
        for claim in ledger.claims:
            lines.append(render_claim(claim))
        unsourced = sum(1 for c in ledger.claims if not c.source_url)
        if unsourced:
            lines += [
                "",
                (
                    f"> {unsourced} of {len(ledger.claims)} claims have no verifiable "
                    "source. Weight them accordingly."
                ),
            ]
    else:
        lines.append(
            "_No verifiable evidence was gathered. Every conclusion above is "
            "unsupported and the score reflects that._"
        )

    return "\n".join(lines) + "\n"
