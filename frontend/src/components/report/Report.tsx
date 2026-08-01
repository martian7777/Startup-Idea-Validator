/**
 * The 16-section opportunity report.
 *
 * Rendered from the structured JSON contract, not from the markdown blob —
 * the markdown exists for download, but reading it on screen would throw away
 * every distinction the schema works to preserve.
 */

import type { OpportunityReport, OpportunityScore } from "@/lib/api";
import { BulletList, Callout, Card, Empty, Prose, Section } from "@/components/ui";
import { ScenarioChart } from "@/components/charts/ScenarioChart";
import { ClaimList } from "@/components/report/Evidence";
import { ScorePanel } from "@/components/report/ScorePanel";
import {
  CompetitorTable,
  CriticPanel,
  InterviewQuestions,
  PersonaCards,
  ScenarioAssumptions,
  ValidationPlan,
} from "@/components/report/Sections";

export const REPORT_SECTIONS = [
  { id: "summary", label: "Executive summary" },
  { id: "score", label: "Opportunity score" },
  { id: "hypothesis", label: "Hypothesis" },
  { id: "problem", label: "Problem analysis" },
  { id: "segments", label: "Customer segments" },
  { id: "market", label: "Market evidence" },
  { id: "competitors", label: "Competitors" },
  { id: "differentiation", label: "Differentiation" },
  { id: "revenue", label: "Revenue model" },
  { id: "financials", label: "Financial scenarios" },
  { id: "assumptions", label: "Key assumptions" },
  { id: "risks", label: "Major risks" },
  { id: "critic", label: "Critic's verdict" },
  { id: "plan", label: "7-day validation plan" },
  { id: "interviews", label: "Interview questions" },
  { id: "sources", label: "Sources" },
];

export function Report({
  report,
  score,
}: {
  report: OpportunityReport | null;
  score: OpportunityScore;
}) {
  if (!report) {
    return (
      <div className="space-y-6">
        <Callout tone="warn" title="The report agent did not complete">
          The score and evidence below reflect what was gathered before the run
          stopped. Treat the sections that are missing as unanswered, not as
          answered favourably.
        </Callout>
        <ScorePanel score={score} />
      </div>
    );
  }

  const marketClaims = [
    ...(report.market_evidence?.problem_evidence ?? []),
    ...(report.market_evidence?.demand_signals ?? []),
    ...(report.market_evidence?.trends ?? []),
  ];

  const allClaims = [
    ...marketClaims,
    ...(report.competitors?.evidence ?? []),
    ...(report.segments?.evidence ?? []),
  ];

  const unsourced = allClaims.filter((claim) => !claim.source_url).length;

  return (
    <div className="space-y-12">
      <Section index={1} id="summary" title="Executive summary">
        <Card>
          <Prose>{report.executive_summary}</Prose>
        </Card>
      </Section>

      <Section
        index={2}
        id="score"
        title="Opportunity score"
        subtitle="Computed from the evidence by a deterministic scorer, not by a model."
      >
        <ScorePanel score={score} />
      </Section>

      <Section
        index={3}
        id="hypothesis"
        title="Startup hypothesis"
        subtitle="Your idea restated as something that could be proven wrong."
      >
        <Card className="space-y-4">
          {[
            ["Problem", report.hypothesis?.problem_statement],
            ["Segment", report.hypothesis?.target_segment],
            ["Solution", report.hypothesis?.proposed_solution],
            ["Value hypothesis", report.hypothesis?.value_hypothesis],
          ].map(([label, value]) =>
            value ? (
              <div key={label as string}>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                  {label as string}
                </p>
                <p className="mt-1 text-[15px] leading-relaxed text-ink-secondary">
                  {value as string}
                </p>
              </div>
            ) : null,
          )}

          {report.hypothesis?.riskiest_assumptions?.length > 0 && (
            <div className="border-t border-hairline pt-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-muted">
                Riskiest assumptions
              </p>
              <BulletList items={report.hypothesis.riskiest_assumptions} tone="risk" />
            </div>
          )}

          {report.hypothesis?.missing_information?.length > 0 && (
            <Callout tone="warn" title="Information you did not supply">
              <BulletList items={report.hypothesis.missing_information} />
            </Callout>
          )}
        </Card>
      </Section>

      <Section index={4} id="problem" title="Problem analysis">
        <Card>
          <Prose>{report.problem_analysis}</Prose>
        </Card>
      </Section>

      <Section
        index={5}
        id="segments"
        title="Target customer segments"
        subtitle="Every persona is a hypothesis until you have interviewed someone."
      >
        <PersonaCards segments={report.segments} />
      </Section>

      <Section
        index={6}
        id="market"
        title="Market evidence"
        subtitle="What the research actually found, with its sources."
      >
        <div className="space-y-4">
          {report.market_evidence?.market_size_notes && (
            <Card>
              <Prose>{report.market_evidence.market_size_notes}</Prose>
            </Card>
          )}
          <ClaimList
            claims={marketClaims}
            emptyMessage="No market evidence was found. That absence is itself the finding — the score reflects it."
          />
          {report.market_evidence?.unknowns?.length > 0 && (
            <Callout tone="warn" title="Still unknown">
              <BulletList items={report.market_evidence.unknowns} />
            </Callout>
          )}
        </div>
      </Section>

      <Section index={7} id="competitors" title="Competitor comparison">
        <div className="space-y-4">
          <CompetitorTable competitors={report.competitors} />
          {report.competitors?.gaps?.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-ink">Gaps identified</h3>
              <BulletList items={report.competitors.gaps} />
            </div>
          )}
        </div>
      </Section>

      <Section index={8} id="differentiation" title="Differentiation opportunities">
        <BulletList items={report.differentiation ?? []} />
      </Section>

      <Section index={9} id="revenue" title="Revenue-model analysis">
        <Card>
          <Prose>{report.revenue_model_analysis}</Prose>
        </Card>
      </Section>

      <Section
        index={10}
        id="financials"
        title="Financial scenarios"
        subtitle="Every number is labelled sourced, calculated, or assumed."
      >
        <div className="space-y-5">
          {report.financials ? (
            <>
              <ScenarioChart financials={report.financials} />

              {report.financials.pricing_rationale && (
                <Card>
                  <h3 className="text-sm font-semibold text-ink">Pricing rationale</h3>
                  <div className="mt-2">
                    <Prose>{report.financials.pricing_rationale}</Prose>
                  </div>
                </Card>
              )}

              <div className="grid gap-4 lg:grid-cols-3">
                <ScenarioAssumptions scenario={report.financials.conservative} />
                <ScenarioAssumptions scenario={report.financials.realistic} />
                <ScenarioAssumptions scenario={report.financials.optimistic} />
              </div>
            </>
          ) : (
            <Empty>No financial model was produced.</Empty>
          )}
        </div>
      </Section>

      <Section index={11} id="assumptions" title="Key assumptions">
        <BulletList items={report.key_assumptions ?? []} tone="risk" />
      </Section>

      <Section index={12} id="risks" title="Major risks">
        <BulletList items={report.major_risks ?? []} tone="risk" />
      </Section>

      <Section
        index={13}
        id="critic"
        title="Critic's verdict"
        subtitle="The critic may lower confidence. It can never raise it."
      >
        <CriticPanel verdict={report.critic_verdict} />
      </Section>

      <Section
        index={14}
        id="plan"
        title="Seven-day validation plan"
        subtitle="Do these before you build anything."
      >
        <ValidationPlan steps={report.validation_plan ?? []} />
      </Section>

      <Section index={15} id="interviews" title="Customer interview questions">
        <InterviewQuestions questions={report.interview_questions ?? []} />
      </Section>

      <Section
        index={16}
        id="sources"
        title="Sources and confidence"
        subtitle={`${allClaims.length} claim${allClaims.length === 1 ? "" : "s"} gathered${
          unsourced ? `, ${unsourced} without a verifiable source` : ""
        }.`}
      >
        <div className="space-y-4">
          {unsourced > 0 && (
            <Callout tone="warn">
              {unsourced} of {allClaims.length} claims have no verifiable source.
              Weight them accordingly.
            </Callout>
          )}
          <ClaimList
            claims={allClaims}
            emptyMessage="No verifiable evidence was gathered. Every conclusion above is unsupported, and the score reflects that."
          />
        </div>
      </Section>
    </div>
  );
}
