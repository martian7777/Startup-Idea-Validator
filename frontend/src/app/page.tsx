"use client";

/** Idea submission and run history. */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, bandStyle, type IdeaSubmission, type RunSummary } from "@/lib/api";
import { Card, cx } from "@/components/ui";

const REVENUE_MODELS = [
  "subscription",
  "one_time",
  "marketplace",
  "advertising",
  "usage_based",
  "freemium",
  "services",
  "other",
];

const EMPTY: IdeaSubmission = {
  idea: "",
  target_customer: "",
  country: "",
  industry: "",
  revenue_model: "subscription",
  monthly_budget_eur: null,
  founder_skills: "",
};

const inputClass =
  "w-full rounded-lg border border-hairline bg-card px-3 py-2 text-sm text-ink " +
  "outline-none transition-colors placeholder:text-ink-muted focus:border-accent";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-ink-muted">{hint}</span>}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

export default function Home() {
  const router = useRouter();
  const [form, setForm] = useState<IdeaSubmission>(EMPTY);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  const tooShort = form.idea.trim().length < 20;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const run = await api.createRun({
        ...form,
        monthly_budget_eur: form.monthly_budget_eur || null,
        founder_skills: form.founder_skills || null,
      });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-6 py-16">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight text-ink">
          Startup Idea Validator
        </h1>
        <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-secondary">
          Six agents research your idea, then challenge each other&apos;s
          findings. You get an evidence-backed report where every claim carries
          its source and every number says whether it was measured or assumed.
        </p>
        <p className="mt-3 max-w-xl border-l-2 border-axis pl-3 text-sm leading-relaxed text-ink-muted">
          The score measures how strong the evidence is — not how likely you are
          to succeed. A low score usually means nobody has proven the problem is
          worth paying to solve yet.
        </p>
      </header>

      <form onSubmit={submit} className="mt-10 space-y-5">
        <Field
          label="Your idea"
          hint="What you would build, and the problem it solves. Specific beats polished."
        >
          <textarea
            required
            rows={5}
            value={form.idea}
            onChange={(e) => setForm({ ...form, idea: e.target.value })}
            className={cx(inputClass, "resize-y leading-relaxed")}
            placeholder="A tool that helps international master's applicants track differing university requirements and deadlines…"
          />
          {form.idea.length > 0 && tooShort && (
            <p className="mt-1.5 text-xs text-ink-secondary">
              At least 20 characters — a thin description produces a thin report.
            </p>
          )}
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Target customer">
            <input
              required
              value={form.target_customer}
              onChange={(e) => setForm({ ...form, target_customer: e.target.value })}
              className={inputClass}
              placeholder="International master's applicants"
            />
          </Field>

          <Field label="Country or market">
            <input
              required
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
              className={inputClass}
              placeholder="Germany"
            />
          </Field>

          <Field label="Industry">
            <input
              required
              value={form.industry}
              onChange={(e) => setForm({ ...form, industry: e.target.value })}
              className={inputClass}
              placeholder="Education technology"
            />
          </Field>

          <Field label="Revenue model">
            <select
              value={form.revenue_model}
              onChange={(e) => setForm({ ...form, revenue_model: e.target.value })}
              className={cx(inputClass, "capitalize")}
            >
              {REVENUE_MODELS.map((model) => (
                <option key={model} value={model}>
                  {model.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Monthly budget (EUR)" hint="Optional">
            <input
              type="number"
              min={0}
              value={form.monthly_budget_eur ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  monthly_budget_eur: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={cx(inputClass, "tabular-nums")}
            />
          </Field>

          <Field label="Your skills" hint="Optional">
            <input
              value={form.founder_skills ?? ""}
              onChange={(e) => setForm({ ...form, founder_skills: e.target.value })}
              className={inputClass}
              placeholder="Full-stack development, no design"
            />
          </Field>
        </div>

        {error && (
          <p className="rounded-lg border border-critical/30 bg-critical/5 px-3 py-2 text-sm text-ink-secondary">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting || tooShort}
          className="rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-page transition-opacity disabled:opacity-30"
        >
          {submitting ? "Starting research…" : "Validate this idea"}
        </button>
      </form>

      {runs.length > 0 && (
        <section className="mt-16">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Previous runs
          </h2>
          <ul className="mt-3 space-y-2">
            {runs.map((run) => {
              const band = bandStyle(run.score_band);
              return (
                <li key={run.id}>
                  <Link href={`/runs/${run.id}`} className="block">
                    <Card className="flex items-center gap-4 transition-colors hover:bg-sunken">
                      {/* The tinted chip carries the band; the number stays in
                          ink so it is legible at any band. */}
                      <span
                        className={cx(
                          "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border text-base font-semibold text-ink",
                          band.bg,
                          band.border,
                        )}
                      >
                        {run.score_total !== null ? Math.round(run.score_total) : "–"}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm text-ink">
                          {run.idea || "Untitled idea"}
                        </span>
                        <span className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-muted">
                          <span aria-hidden className={band.text}>
                            {band.glyph}
                          </span>
                          <span>{band.short}</span>
                          <span>·</span>
                          <span>{run.status}</span>
                          {run.error && (
                            <span className="truncate">· {run.error.slice(0, 60)}</span>
                          )}
                        </span>
                      </span>
                    </Card>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
