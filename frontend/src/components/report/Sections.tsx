/** The structural report sections: competitors, personas, critic, plan. */

import type {
  CompetitorSet,
  CriticVerdict,
  Number_,
  PersonaSet,
  Scenario,
  ValidationStep,
} from "@/lib/api";
import { BulletList, Callout, Card, Empty, Prose, cx } from "@/components/ui";

// --- Competitors ----------------------------------------------------------

export function CompetitorTable({ competitors }: { competitors: CompetitorSet }) {
  const rows = [
    ...(competitors.direct ?? []).map((c) => ({ ...c, kind: "Direct" as const })),
    ...(competitors.indirect ?? []).map((c) => ({ ...c, kind: "Indirect" as const })),
  ];

  if (!rows.length) {
    return (
      <Callout tone="warn" title="No competitors identified">
        This is usually a warning sign rather than an opportunity. It normally
        means the search was too narrow, or that no market exists — not that the
        space is empty and waiting.
      </Callout>
    );
  }

  return (
    <Card padded={false}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-ink-muted">
              <th scope="col" className="px-4 py-3 font-medium">Competitor</th>
              <th scope="col" className="px-4 py-3 font-medium">Target user</th>
              <th scope="col" className="px-4 py-3 font-medium">Pricing</th>
              <th scope="col" className="px-4 py-3 font-medium">Strengths</th>
              <th scope="col" className="px-4 py-3 font-medium">Weaknesses</th>
              <th scope="col" className="px-4 py-3 font-medium">Opening</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((competitor, index) => (
              <tr
                key={`${competitor.name}-${index}`}
                className="border-b border-hairline align-top last:border-0"
              >
                <th scope="row" className="px-4 py-3 text-left font-medium text-ink">
                  {competitor.source_url ? (
                    <a
                      href={competitor.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent underline-offset-2 hover:underline"
                    >
                      {competitor.name}
                    </a>
                  ) : (
                    competitor.name
                  )}
                  <span className="mt-0.5 block text-xs font-normal text-ink-muted">
                    {competitor.kind}
                  </span>
                </th>
                <td className="px-4 py-3 text-ink-secondary">{competitor.target_user}</td>
                <td className="px-4 py-3 tabular-nums text-ink-secondary">
                  {competitor.pricing ?? "—"}
                </td>
                <td className="px-4 py-3 text-ink-secondary">
                  {competitor.strengths?.join("; ") || "—"}
                </td>
                <td className="px-4 py-3 text-ink-secondary">
                  {competitor.weaknesses?.join("; ") || "—"}
                </td>
                <td className="px-4 py-3 text-ink-secondary">
                  {competitor.opportunity ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// --- Personas -------------------------------------------------------------

export function PersonaCards({ segments }: { segments: PersonaSet }) {
  if (!segments?.personas?.length) {
    return <Empty>No customer segments were produced.</Empty>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {segments.personas.map((persona, index) => (
        <Card key={index} className="flex flex-col gap-3">
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-ink">{persona.name}</h3>
            {persona.is_early_adopter && (
              <span className="shrink-0 rounded-full border border-hairline px-2 py-0.5 text-[11px] text-ink-secondary">
                Likely early adopter
              </span>
            )}
          </div>

          <p className="text-sm leading-relaxed text-ink-secondary">
            {persona.description}
          </p>

          {[
            ["Jobs to be done", persona.jobs_to_be_done],
            ["Pains", persona.pains],
            ["Uses today", persona.current_alternatives],
          ].map(([label, values]) =>
            (values as string[])?.length ? (
              <div key={label as string}>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                  {label as string}
                </p>
                <p className="mt-1 text-sm text-ink-secondary">
                  {(values as string[]).join(" · ")}
                </p>
              </div>
            ) : null,
          )}

          {persona.willingness_to_pay_hypothesis && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                Willingness to pay (hypothesis)
              </p>
              <p className="mt-1 text-sm text-ink-secondary">
                {persona.willingness_to_pay_hypothesis}
              </p>
            </div>
          )}

          {/* A persona is a hypothesis until someone is interviewed. Never let
              the card imply otherwise. Colour rides the glyph, not the text —
              `serious` is below 3:1 on the light surface. */}
          <p className="mt-auto flex items-center gap-2 border-t border-hairline pt-3 text-xs text-ink-secondary">
            <span aria-hidden className="text-serious">◆</span>
            {persona.validation_status}
          </p>
        </Card>
      ))}
    </div>
  );
}

// --- Numbers --------------------------------------------------------------

const PROVENANCE_COPY: Record<string, { label: string; className: string }> = {
  sourced: { label: "Sourced", className: "text-ink-secondary" },
  calculated: { label: "Calculated", className: "text-ink-secondary" },
  assumed: { label: "Assumed", className: "text-critical font-semibold" },
};

export function NumberRow({ number }: { number: Number_ }) {
  if (!number) return null;
  const provenance = PROVENANCE_COPY[number.provenance] ?? PROVENANCE_COPY.assumed;

  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-hairline py-2 last:border-0">
      <span className="text-sm text-ink-secondary">{number.label}</span>
      <span className="flex items-baseline gap-2">
        <span className="tabular-nums text-sm font-medium text-ink">
          {number.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          <span className="ml-1 text-xs font-normal text-ink-muted">
            {number.unit}
          </span>
        </span>
        <span className={cx("text-[11px] uppercase tracking-wide", provenance.className)}>
          {provenance.label}
        </span>
      </span>
      {(number.formula || number.rationale) && (
        <p className="w-full text-xs text-ink-muted">
          {number.formula ? (
            <code className="font-mono">{number.formula}</code>
          ) : (
            <>You are being asked to accept: {number.rationale}</>
          )}
        </p>
      )}
    </div>
  );
}

export function ScenarioAssumptions({ scenario }: { scenario: Scenario }) {
  if (!scenario) return null;
  const numbers = [
    scenario.monthly_revenue,
    scenario.monthly_costs,
    scenario.break_even_customers,
    ...(scenario.assumptions ?? []),
  ].filter(Boolean);

  return (
    <Card>
      <h3 className="text-sm font-semibold capitalize text-ink">
        {scenario.name}
      </h3>
      <div className="mt-2">
        {numbers.map((number, index) => (
          <NumberRow key={number.id ?? index} number={number} />
        ))}
      </div>
      {scenario.notes && (
        <p className="mt-3 text-sm leading-relaxed text-ink-secondary">
          {scenario.notes}
        </p>
      )}
    </Card>
  );
}

// --- Critic ---------------------------------------------------------------

export function CriticPanel({ verdict }: { verdict: CriticVerdict }) {
  if (!verdict) return <Empty>The critic did not return a verdict.</Empty>;

  return (
    <div className="space-y-4">
      <Card>
        <Prose>{verdict.summary}</Prose>
        <p className="mt-4 border-l-2 border-critical pl-3 text-[15px] font-semibold text-ink">
          {verdict.verdict}
        </p>
      </Card>

      {verdict.contradictions?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">
            Contradictions between agents
          </h3>
          <ul className="space-y-2">
            {verdict.contradictions.map((contradiction, index) => (
              <li
                key={index}
                className="flex items-start gap-3 rounded-lg border border-hairline bg-card px-4 py-3 text-sm"
              >
                <span aria-hidden className="mt-0.5 text-critical">■</span>
                <span className="text-ink-secondary">
                  {contradiction.description}
                  <span className="ml-2 text-xs text-ink-muted">
                    ({contradiction.severity})
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {verdict.unsupported_claims?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">
            Claims with no supporting source
          </h3>
          <BulletList items={verdict.unsupported_claims} tone="risk" />
        </div>
      )}

      {verdict.outdated_sources?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">Outdated sources</h3>
          <BulletList items={verdict.outdated_sources} tone="risk" />
        </div>
      )}

      <Callout tone="critical" title="You must validate these yourself">
        <ul className="mt-2 space-y-2">
          {verdict.must_validate_manually?.map((item, index) => (
            <li key={index} className="flex gap-3">
              <span aria-hidden className="mt-[0.55rem] h-1 w-1 shrink-0 rounded-full bg-critical" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Callout>
    </div>
  );
}

// --- Validation plan ------------------------------------------------------

export function ValidationPlan({ steps }: { steps: ValidationStep[] }) {
  if (!steps?.length) return <Empty>No validation plan was produced.</Empty>;
  const ordered = [...steps].sort((a, b) => a.day - b.day);

  return (
    <ol className="relative space-y-3 border-l border-hairline pl-6">
      {ordered.map((step, index) => (
        <li key={index} className="relative">
          <span
            aria-hidden
            className="absolute -left-[1.8125rem] top-1 flex h-5 w-5 items-center justify-center rounded-full border border-hairline bg-card text-[10px] font-semibold tabular-nums text-ink-secondary"
          >
            {step.day}
          </span>
          <div className="rounded-lg border border-hairline bg-card px-4 py-3">
            <p className="text-sm text-ink">{step.action}</p>
            <p className="mt-1.5 text-xs text-ink-muted">
              <span className="font-medium text-ink-secondary">Success signal: </span>
              {step.success_signal}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

// --- Interview questions --------------------------------------------------

export function InterviewQuestions({ questions }: { questions: string[] }) {
  if (!questions?.length) return <Empty>No interview questions were produced.</Empty>;

  return (
    <ol className="space-y-2">
      {questions.map((question, index) => (
        <li
          key={index}
          className="flex gap-3 rounded-lg border border-hairline bg-card px-4 py-3 text-sm"
        >
          <span className="shrink-0 font-mono text-xs tabular-nums text-ink-muted">
            {String(index + 1).padStart(2, "0")}
          </span>
          <span className="text-ink-secondary">{question}</span>
        </li>
      ))}
    </ol>
  );
}
