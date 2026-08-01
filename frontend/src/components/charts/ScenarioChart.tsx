"use client";

/**
 * Financial scenarios.
 *
 * Form: grouped columns, revenue against costs across the three scenarios.
 * The question a founder actually has here is "does it clear its costs, and
 * under which assumptions" — a magnitude comparison, so columns.
 *
 * Break-even customers are deliberately NOT on this chart. They are a
 * different unit (customers, not currency), and putting them on a second
 * y-axis would invent a relationship the data does not contain. They get stat
 * tiles instead.
 *
 * Colours are validated categorical slots 1 and 2. Both modes clear CVD
 * separation, chroma floor, lightness band and 3:1 contrast against their
 * surface. A legend is always present (two series) and every value is also
 * reachable in the table view below, so nothing is gated behind hover.
 */

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatMoney, type FinancialScenarios, type Number_ } from "@/lib/api";
import { Card, StatTile, cx } from "@/components/ui";

const SERIES = [
  { key: "revenue", label: "Monthly revenue", varName: "--series-1" },
  { key: "costs", label: "Monthly costs", varName: "--series-2" },
] as const;

interface Row {
  scenario: string;
  revenue: number;
  costs: number;
  revenueNumber: Number_;
  costsNumber: Number_;
}

/**
 * Round axis ticks to 1/2/2.5/5 × 10ⁿ steps.
 *
 * Recharts' default domain produces ticks like 3.5K / 7.0K / 11K, which are
 * harder to read off than they look — the axis carries every value that isn't
 * directly labelled, so the steps have to be numbers a reader can hold.
 */
function niceTicks(max: number, target = 4): { ticks: number[]; top: number } {
  if (!Number.isFinite(max) || max <= 0) return { ticks: [0, 1], top: 1 };

  const rawStep = max / target;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalised = rawStep / magnitude;
  const niceStep =
    (normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 2.5 ? 2.5 : normalised <= 5 ? 5 : 10) *
    magnitude;

  const top = Math.ceil(max / niceStep) * niceStep;
  const ticks: number[] = [];
  for (let value = 0; value <= top + niceStep / 2; value += niceStep) {
    ticks.push(Math.round(value * 1e6) / 1e6);
  }
  return { ticks, top };
}

/** Axis ticks drop trailing decimals so the column reads evenly. */
function formatTick(value: number, unit: string): string {
  const symbol = unit.toUpperCase() === "EUR" ? "€" : unit.toUpperCase() === "USD" ? "$" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${symbol}${trim(value / 1_000_000)}M`;
  if (abs >= 1_000) return `${symbol}${trim(value / 1_000)}K`;
  return `${symbol}${trim(value)}`;
}

function trim(value: number): string {
  return Number(value.toFixed(1)).toString();
}

function useTokens() {
  // Recharts needs concrete colours, not CSS vars, so the tokens are resolved
  // from the document and re-read when the colour scheme changes.
  const [tokens, setTokens] = useState({
    series1: "#2a78d6",
    series2: "#eb6834",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    muted: "#898781",
    card: "#fcfcfb",
    ink: "#0b0b0b",
    inkSecondary: "#52514e",
  });

  useEffect(() => {
    const read = () => {
      const style = getComputedStyle(document.documentElement);
      const value = (name: string, fallback: string) =>
        style.getPropertyValue(name).trim() || fallback;
      setTokens({
        series1: value("--series-1", "#2a78d6"),
        series2: value("--series-2", "#eb6834"),
        grid: value("--line-grid", "#e1e0d9"),
        axis: value("--line-axis", "#c3c2b7"),
        muted: value("--ink-muted", "#898781"),
        card: value("--surface-card", "#fcfcfb"),
        ink: value("--ink-primary", "#0b0b0b"),
        inkSecondary: value("--ink-secondary", "#52514e"),
      });
    };
    read();

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", read);
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => {
      media.removeEventListener("change", read);
      observer.disconnect();
    };
  }, []);

  return tokens;
}

function ChartTooltip({
  active,
  payload,
  label,
  tokens,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number }>;
  label?: string;
  tokens: ReturnType<typeof useTokens>;
}) {
  if (!active || !payload?.length) return null;

  const revenue = payload.find((p) => p.dataKey === "revenue")?.value ?? 0;
  const costs = payload.find((p) => p.dataKey === "costs")?.value ?? 0;
  const margin = revenue - costs;

  return (
    <div className="rounded-lg border border-hairline bg-card px-3 py-2 shadow-sm">
      <p className="text-xs font-semibold capitalize text-ink">{label}</p>
      <dl className="mt-1.5 space-y-1">
        {SERIES.map((series) => {
          const value = payload.find((p) => p.dataKey === series.key)?.value ?? 0;
          return (
            <div key={series.key} className="flex items-center gap-2 text-xs">
              <span
                aria-hidden
                className="h-2 w-2 shrink-0 rounded-[2px]"
                style={{
                  background:
                    series.key === "revenue" ? tokens.series1 : tokens.series2,
                }}
              />
              <dt className="text-ink-secondary">{series.label}</dt>
              <dd className="ml-auto tabular-nums font-medium text-ink">
                {formatMoney(value)}
              </dd>
            </div>
          );
        })}
        <div className="mt-1 flex items-center gap-2 border-t border-hairline pt-1 text-xs">
          <dt className="text-ink-secondary">Margin</dt>
          <dd
            className={cx(
              "ml-auto tabular-nums font-semibold",
              margin >= 0 ? "text-good" : "text-critical",
            )}
          >
            {margin >= 0 ? "+" : "−"}
            {formatMoney(Math.abs(margin))}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function ScenarioChart({ financials }: { financials: FinancialScenarios }) {
  const tokens = useTokens();
  const [showTable, setShowTable] = useState(false);

  const scenarios = [
    financials.conservative,
    financials.realistic,
    financials.optimistic,
  ].filter(Boolean);

  const rows: Row[] = scenarios.map((scenario) => ({
    scenario: scenario.name,
    revenue: scenario.monthly_revenue?.value ?? 0,
    costs: scenario.monthly_costs?.value ?? 0,
    revenueNumber: scenario.monthly_revenue,
    costsNumber: scenario.monthly_costs,
  }));

  const currency = financials.realistic?.monthly_revenue?.unit ?? "EUR";
  const { ticks, top } = niceTicks(
    Math.max(0, ...rows.flatMap((row) => [row.revenue, row.costs])),
  );

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink">
              Revenue against costs, by scenario
            </h3>
            <p className="mt-0.5 text-xs text-ink-secondary">
              Monthly, in {currency}. Assumptions differ per scenario — check
              their provenance below.
            </p>
          </div>

          {/* Legend: always present for two or more series. */}
          <ul className="flex items-center gap-4">
            {SERIES.map((series) => (
              <li key={series.key} className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className="h-2.5 w-2.5 rounded-[2px]"
                  style={{
                    background:
                      series.key === "revenue" ? tokens.series1 : tokens.series2,
                  }}
                />
                <span className="text-xs text-ink-secondary">
                  {series.label}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Height includes the x-axis band so the axis is never clipped. */}
        <div className="mt-5 h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              margin={{ top: 8, right: 8, bottom: 4, left: 4 }}
              barGap={2}
            >
              <CartesianGrid
                vertical={false}
                stroke={tokens.grid}
                strokeWidth={1}
              />
              <XAxis
                dataKey="scenario"
                tickLine={false}
                axisLine={{ stroke: tokens.axis, strokeWidth: 1 }}
                tick={{ fill: tokens.muted, fontSize: 12 }}
                tickFormatter={(value: string) =>
                  value.charAt(0).toUpperCase() + value.slice(1)
                }
                className="capitalize"
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={56}
                domain={[0, top]}
                ticks={ticks}
                tick={{ fill: tokens.muted, fontSize: 11 }}
                tickFormatter={(value: number) => formatTick(value, currency)}
              />
              <Tooltip
                cursor={{ fill: tokens.grid, fillOpacity: 0.35 }}
                content={<ChartTooltip tokens={tokens} />}
              />
              {SERIES.map((series) => (
                <Bar
                  key={series.key}
                  dataKey={series.key}
                  maxBarSize={24}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                >
                  {rows.map((row) => (
                    <Cell
                      key={`${series.key}-${row.scenario}`}
                      fill={
                        series.key === "revenue" ? tokens.series1 : tokens.series2
                      }
                      // 2px surface gap does the separating between neighbours.
                      stroke={tokens.card}
                      strokeWidth={2}
                    />
                  ))}
                </Bar>
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>

        <button
          type="button"
          onClick={() => setShowTable((open) => !open)}
          className="mt-3 text-xs font-medium text-accent underline-offset-2 hover:underline"
        >
          {showTable ? "Hide table view" : "Show table view"}
        </button>

        {showTable && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <caption className="sr-only">
                Monthly revenue and costs by scenario
              </caption>
              <thead>
                <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-ink-muted">
                  <th scope="col" className="py-2 pr-3 font-medium">Scenario</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Revenue</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Costs</th>
                  <th scope="col" className="py-2 text-right font-medium">Margin</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const margin = row.revenue - row.costs;
                  return (
                    <tr key={row.scenario} className="border-b border-hairline last:border-0">
                      <th scope="row" className="py-2 pr-3 text-left font-normal capitalize text-ink">
                        {row.scenario}
                      </th>
                      <td className="py-2 pr-3 text-right tabular-nums text-ink-secondary">
                        {formatMoney(row.revenue, currency)}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums text-ink-secondary">
                        {formatMoney(row.costs, currency)}
                      </td>
                      <td
                        className={cx(
                          "py-2 text-right tabular-nums font-medium",
                          margin >= 0 ? "text-good" : "text-critical",
                        )}
                      >
                        {margin >= 0 ? "+" : "−"}
                        {formatMoney(Math.abs(margin), currency)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Different unit, so a separate encoding rather than a second axis. */}
      <div className="grid gap-3 sm:grid-cols-3">
        {scenarios.map((scenario) => (
          <StatTile
            key={scenario.name}
            label={`${scenario.name} break-even`}
            value={Math.round(
              scenario.break_even_customers?.value ?? 0,
            ).toLocaleString()}
            unit="customers"
            footnote={
              scenario.break_even_customers?.provenance === "assumed"
                ? "Rests on an assumption"
                : scenario.break_even_customers?.formula ?? undefined
            }
            tone={
              scenario.break_even_customers?.provenance === "assumed"
                ? "muted"
                : "default"
            }
          />
        ))}
      </div>
    </div>
  );
}
