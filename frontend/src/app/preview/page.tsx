"use client";

/**
 * Design preview with fixture data.
 *
 * Exists so the report can be inspected without a live Gemini run — layout,
 * label collisions, chart geometry and the light/dark treatments all need to
 * be looked at, and a validator cannot do that. Not linked from the app.
 */

import { Report } from "@/components/report/Report";
import { RunProgress } from "@/components/RunProgress";
import type { OpportunityReport, OpportunityScore } from "@/lib/api";

const claim = (
  text: string,
  overrides: Partial<{
    kind: "fact" | "estimate" | "assumption";
    strength: "strong" | "moderate" | "weak" | "anecdotal";
    url: string | null;
    date: string | null;
    confidence: number;
  }> = {},
) => ({
  id: Math.random().toString(36).slice(2),
  text,
  kind: overrides.kind ?? ("fact" as const),
  evidence_strength: overrides.strength ?? ("strong" as const),
  confidence: overrides.confidence ?? 0.85,
  source_url: overrides.url === undefined ? "https://example.org/study-2026" : overrides.url,
  source_title: overrides.url === null ? null : "DAAD Applicant Survey 2026",
  published_date: overrides.date === undefined ? "2026-02-14" : overrides.date,
});

const number = (
  label: string,
  value: number,
  unit: string,
  provenance: "sourced" | "calculated" | "assumed",
  extra: { formula?: string; rationale?: string } = {},
) => ({
  id: Math.random().toString(36).slice(2),
  label,
  value,
  unit,
  provenance,
  formula: extra.formula ?? null,
  source_claim_id: provenance === "sourced" ? "abc" : null,
  rationale: extra.rationale ?? null,
});

const SCORE: OpportunityScore = {
  total: 61.4,
  band: "promising",
  band_label: "Promising, but major assumptions need testing",
  disclaimer:
    "This score measures the strength of the evidence gathered, not the likelihood of success. A high score means the idea survived scrutiny so far; it is not a prediction and does not substitute for talking to real customers.",
  penalty_points: 4,
  penalties: ["-4.0 for 1 unresolved contradiction(s) between agents."],
  categories: [
    ["problem_severity", 20, 0.9, 0.82, "strong", 6],
    ["demand_evidence", 20, 0.85, 0.48, "moderate", 3],
    ["market_attractiveness", 15, 0.8, 0.71, "moderate", 4],
    ["differentiation", 15, 0.75, 0.6, "moderate", 2],
    ["business_model", 10, 0.7, 0.35, "weak", 1],
    ["acquisition_feasibility", 10, 0.6, 0.25, "anecdotal", 1],
    ["execution_feasibility", 10, 0.8, 0.25, null, 0],
  ].map(([category, weight, proposed, effective, best, claims]) => ({
    category: category as string,
    weight: weight as number,
    proposed_rating: proposed as number,
    effective_rating: effective as number,
    points: (effective as number) * (weight as number),
    max_points: weight as number,
    best_evidence: best as never,
    supporting_claims: claims as number,
    evidence_coverage: 0.6,
    adjustments:
      (effective as number) < (proposed as number)
        ? [
            `Rating capped ${(proposed as number).toFixed(2)} → ${(effective as number).toFixed(2)}: best evidence is ${best ?? "no supporting evidence"}.`,
          ]
        : [],
  })),
};

const REPORT: OpportunityReport = {
  executive_summary:
    "There is credible evidence that international applicants lose time reconciling inconsistent university requirements, and that the pain concentrates around deadline tracking. What is not established is that anyone currently pays to solve it: the strongest demand signals found were forum complaints and one consultancy's pricing page, neither of which demonstrates willingness to pay for software.",
  problem_analysis:
    "Applicants to German master's programmes typically apply to between four and nine institutions, each publishing requirements in a different structure and often only in German. The recurring failure is not finding information but reconciling contradictory versions of it.",
  hypothesis: {
    problem_statement:
      "International master's applicants miss deadlines and mis-submit documents because requirements differ per institution and are published inconsistently.",
    target_segment: "Non-EU applicants to German master's programmes",
    proposed_solution:
      "A tracker that normalises per-university requirements into one checklist with deadline reminders.",
    value_hypothesis:
      "Applicants will pay a one-off fee per application cycle to avoid a missed deadline.",
    riskiest_assumptions: [
      "That applicants will pay rather than use a free spreadsheet",
      "That requirement data can be kept accurate without manual curation per intake",
      "That the pain is acute enough to act on before a deadline is actually missed",
    ],
    research_questions: [
      "Do applicants currently pay anyone to help with this?",
      "How many applications does a typical applicant submit?",
      "What proportion miss a deadline at least once?",
    ],
    missing_information: [
      "Whether you intend to cover only Germany or the wider EU",
      "Whether universities will permit automated requirement scraping",
    ],
  },
  segments: {
    personas: [
      {
        name: "Non-EU applicant, first cycle",
        description:
          "Applying to 5–8 German programmes from outside the EU, working in a second language, with no institutional support.",
        jobs_to_be_done: [
          "Track what each university needs",
          "Avoid missing a submission window",
        ],
        pains: [
          "Contradictory information between the programme page and the admissions office",
          "Deadlines that differ by faculty",
        ],
        current_alternatives: ["Spreadsheets", "WhatsApp groups", "Paid consultants"],
        willingness_to_pay_hypothesis: "€10–€30 per application cycle",
        is_early_adopter: true,
        validation_status: "Unconfirmed — requires customer interviews",
      },
      {
        name: "Agency counsellor",
        description:
          "Manages 20–60 applicants per cycle and already maintains internal trackers.",
        jobs_to_be_done: ["Track many applicants at once"],
        pains: ["Rebuilding the same tracker every intake"],
        current_alternatives: ["Internal spreadsheets"],
        willingness_to_pay_hypothesis: null,
        is_early_adopter: false,
        validation_status: "Unconfirmed — requires customer interviews",
      },
    ],
    interview_questions: [],
    evidence: [
      claim("Counsellors report rebuilding trackers each intake", {
        strength: "weak",
        confidence: 0.45,
        url: null,
        date: null,
        kind: "estimate",
      }),
    ],
  },
  market_evidence: {
    problem_evidence: [
      claim(
        "62% of surveyed international applicants reported confusion about documentation requirements.",
      ),
      claim(
        "Applicants submit to a median of 6 institutions per cycle, each with distinct requirements.",
        { strength: "moderate", confidence: 0.7, date: "2024-09-01" },
      ),
      claim("A 2019 study found similar confusion across EU-wide applications.", {
        strength: "moderate",
        confidence: 0.6,
        date: "2019-05-20",
      }),
    ],
    demand_signals: [
      claim("A Reddit thread on missed deadlines drew 400 upvotes.", {
        kind: "estimate",
        strength: "anecdotal",
        confidence: 0.3,
        url: "https://example.org/thread",
        date: null,
      }),
      claim(
        "Consultancies in this space charge €200–€800 per applicant, indicating some willingness to pay for help.",
        { strength: "moderate", confidence: 0.65, date: "2026-01-10" },
      ),
    ],
    trends: [],
    market_size_notes:
      "No credible total-addressable-market figure was found for this niche. Published figures cover international education broadly and would overstate the reachable market by a wide margin, so none is quoted here.",
    unknowns: [
      "Whether applicants pay for software rather than human help",
      "Renewal behaviour beyond a single application cycle",
    ],
  },
  competitors: {
    direct: [
      {
        name: "Uni-Assist",
        target_user: "Applicants to German universities",
        pricing: "€75 first application",
        strengths: ["Official standing", "Broad coverage"],
        weaknesses: ["Not a tracker", "Poor interface"],
        opportunity: "Tracking layer on top",
        source_url: "https://example.org/uni-assist",
      },
      {
        name: "StudyPortals",
        target_user: "Prospective students",
        pricing: "Free, ad-funded",
        strengths: ["Large catalogue", "Strong SEO"],
        weaknesses: ["Discovery only, no deadline tracking"],
        opportunity: "Post-shortlist workflow",
        source_url: null,
      },
    ],
    indirect: [
      {
        name: "Notion / spreadsheets",
        target_user: "Self-organising applicants",
        pricing: "Free",
        strengths: ["Flexible", "Already adopted"],
        weaknesses: ["Manual data entry", "No requirement updates"],
        opportunity: "Pre-filled, maintained requirement data",
        source_url: null,
      },
    ],
    gaps: [
      "No product combines maintained requirement data with per-applicant deadline tracking",
      "Nothing serves the post-shortlist, pre-submission window",
    ],
    evidence: [
      claim("Uni-Assist charges €75 for the first application.", {
        strength: "strong",
        date: "2026-03-02",
      }),
    ],
  },
  differentiation: [
    "Maintained requirement data rather than a blank template",
    "Deadline tracking scoped to the application cycle, not the whole search",
    "Language normalisation between German programme pages and English summaries",
  ],
  revenue_model_analysis:
    "A one-off per-cycle fee fits the usage pattern better than a subscription: the need is acute for roughly three months and then disappears entirely. Subscription pricing would optimise for a retention that this problem does not naturally produce.",
  financials: {
    pricing_rationale:
      "Pricing is anchored to the €200–€800 consultancy range as a ceiling and to free spreadsheets as a floor. No direct evidence of software willingness-to-pay was found, so all three scenarios rest on an assumed price point.",
    conservative: {
      name: "conservative",
      monthly_revenue: number("Monthly revenue", 1200, "EUR", "calculated", {
        formula: "paying_customers × monthly_price",
      }),
      monthly_costs: number("Monthly costs", 2100, "EUR", "assumed", {
        rationale: "Hosting, data curation and one part-time contractor",
      }),
      break_even_customers: number("Break-even customers", 140, "customers", "calculated", {
        formula: "fixed_costs / (price − variable_cost)",
      }),
      assumptions: [
        number("Monthly price", 15, "EUR", "assumed", {
          rationale: "No pricing evidence for this segment was found",
        }),
      ],
      notes: "Assumes slow adoption and high churn between intake cycles.",
    },
    realistic: {
      name: "realistic",
      monthly_revenue: number("Monthly revenue", 4800, "EUR", "calculated", {
        formula: "paying_customers × monthly_price",
      }),
      monthly_costs: number("Monthly costs", 3200, "EUR", "assumed", {
        rationale: "Adds a second contractor during peak intake",
      }),
      break_even_customers: number("Break-even customers", 215, "customers", "calculated", {
        formula: "fixed_costs / (price − variable_cost)",
      }),
      assumptions: [],
      notes: null,
    },
    optimistic: {
      name: "optimistic",
      monthly_revenue: number("Monthly revenue", 12400, "EUR", "calculated", {
        formula: "paying_customers × monthly_price",
      }),
      monthly_costs: number("Monthly costs", 5100, "EUR", "assumed", {
        rationale: "Assumes agency deals requiring account management",
      }),
      break_even_customers: number("Break-even customers", 340, "customers", "calculated", {
        formula: "fixed_costs / (price − variable_cost)",
      }),
      assumptions: [],
      notes: "Requires agency channel to convert, which is unevidenced.",
    },
  },
  key_assumptions: [
    "Applicants will pay for software rather than use a free spreadsheet",
    "Requirement data can be maintained at acceptable cost",
    "One cycle of usage is enough to justify acquisition cost",
  ],
  major_risks: [
    "Universities may prohibit automated collection of requirement data",
    "Demand is seasonal and collapses outside intake windows",
    "Uni-Assist could add tracking and foreclose the gap",
  ],
  critic_verdict: {
    summary:
      "The problem evidence is genuinely good. The demand evidence is not: a popular forum thread and a consultancy price list do not establish that applicants will pay for software. The financial model treats an assumed price point as though it were observed, and the optimistic scenario depends on an agency channel with no supporting evidence at all.",
    verdict: "Problem is real. Willingness to pay is unproven.",
    contradictions: [
      {
        description:
          "The market agent treats consultancy pricing as evidence of software demand, while the persona agent lists free spreadsheets as the dominant alternative.",
        agents_involved: ["market", "persona"],
        severity: "high",
      },
    ],
    unsupported_claims: [
      "That applicants will pay €10–€30 per cycle — no source supports this figure",
      "That agencies represent a reachable channel",
    ],
    outdated_sources: [
      "The 2019 EU-wide confusion study predates several admissions reforms",
    ],
    unsound_categories: ["business_model"],
    must_validate_manually: [
      "Interview 10 applicants who have completed a cycle; ask what they paid for, not what they would pay for",
      "Confirm at least three universities permit automated requirement collection",
      "Test a paid pre-order page before building the tracker",
    ],
  },
  validation_plan: [
    { day: 1, action: "Post in three applicant communities asking how people track requirements today.", success_signal: "10+ substantive replies describing a manual workaround" },
    { day: 2, action: "Recruit 10 applicants who finished a cycle in the last year.", success_signal: "6+ agree to a 20-minute call" },
    { day: 3, action: "Run the first five interviews, asking only about past behaviour.", success_signal: "3+ describe having paid for help of any kind" },
    { day: 4, action: "Run the remaining interviews and tally what people actually paid for.", success_signal: "A repeated paid workaround emerges" },
    { day: 5, action: "Check the terms of three university sites for automated collection.", success_signal: "At least two permit it or offer an API" },
    { day: 6, action: "Put up a pre-order page at €19 per cycle.", success_signal: "3+ payment attempts from 100 visitors" },
    { day: 7, action: "Decide: build, re-scope to agencies, or stop.", success_signal: "A decision written down with the evidence behind it" },
  ],
  interview_questions: [
    "Walk me through the last time you applied — what did you actually do to keep track?",
    "What did that cost you, in money or in time?",
    "Have you ever paid anyone for help with an application? What for?",
    "What happened the last time you nearly missed a deadline?",
    "What would have to be true for you to stop using your current method?",
  ],
};

const STAGES = {
  manager: "done" as const,
  market_search: "done" as const,
  competitor_search: "running" as const,
  persona_search: "running" as const,
  financial: "pending" as const,
  critic: "pending" as const,
  reporter: "pending" as const,
};

export default function PreviewPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-12 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Design preview
        </h1>
        <p className="mt-2 text-sm text-ink-secondary">
          Fixture data. Not linked from the app.
        </p>
      </div>

      <RunProgress stageStates={STAGES} />
      <Report report={REPORT} score={SCORE} />
    </main>
  );
}
