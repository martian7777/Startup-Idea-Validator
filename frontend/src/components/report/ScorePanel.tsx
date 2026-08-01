/**
 * Score display.
 *
 * The number is the hero, but the "why it was held down" list sits directly
 * beneath it on purpose — that reasoning is the part a founder learns from,
 * and burying it turns an evidence audit back into a vanity metric.
 *
 * The band uses the reserved status palette and always ships with its glyph
 * and label, so the state never rests on hue alone.
 */

import { bandStyle, type OpportunityScore } from "@/lib/api";
import { Card, cx } from "@/components/ui";

function label(category: string) {
  return category.replace(/_/g, " ");
}

/** Proportion of a category's points earned, as a hairline meter. */
function CategoryMeter({ points, max }: { points: number; max: number }) {
  const pct = max > 0 ? Math.max(0, Math.min(1, points / max)) : 0;
  return (
    <span className="flex h-1 w-full overflow-hidden rounded-full bg-ink-muted/15">
      <span
        className="h-full rounded-full bg-accent"
        style={{ width: `${pct * 100}%` }}
      />
    </span>
  );
}

export function ScorePanel({ score }: { score: OpportunityScore }) {
  const band = bandStyle(score.band);
  const adjustments = score.categories.flatMap((category) =>
    category.adjustments.map((text) => ({ category: category.category, text })),
  );

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <div>
          {/*
           * Hero figure in primary ink, not the band colour. Two of the four
           * status steps sit below 3:1 on the light surface, so colouring the
           * largest number on the page with them would make it the least
           * legible thing here. The band reads from the chip beside it.
           */}
          <p className="text-6xl font-semibold leading-none text-ink">
            {Math.round(score.total)}
            <span className="ml-1 text-2xl font-normal text-ink-muted">/100</span>
          </p>
        </div>

        <div
          className={cx(
            "flex items-center gap-2 rounded-full border px-3 py-1.5",
            band.bg,
            band.border,
          )}
        >
          {/* Colour rides the mark; the label stays in ink. */}
          <span aria-hidden className={band.text}>{band.glyph}</span>
          <span className="text-sm font-medium text-ink">
            {score.band_label}
          </span>
        </div>
      </div>

      <p className="mt-4 border-l-2 border-axis pl-3 text-sm leading-relaxed text-ink-secondary">
        {score.disclaimer}
      </p>

      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <caption className="sr-only">Score breakdown by category</caption>
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-ink-muted">
              <th scope="col" className="py-2 pr-4 font-medium">Category</th>
              <th scope="col" className="w-28 py-2 pr-4 font-medium">Earned</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Claimed</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">Allowed</th>
              <th scope="col" className="py-2 font-medium">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {score.categories.map((category) => {
              const capped =
                category.effective_rating < category.proposed_rating - 1e-9;
              return (
                <tr
                  key={category.category}
                  className="border-b border-hairline last:border-0"
                >
                  <th
                    scope="row"
                    className="py-2.5 pr-4 text-left font-normal capitalize text-ink"
                  >
                    {label(category.category)}
                  </th>
                  <td className="py-2.5 pr-4">
                    <span className="flex items-center gap-2">
                      <CategoryMeter
                        points={category.points}
                        max={category.max_points}
                      />
                      <span className="shrink-0 tabular-nums text-xs text-ink-secondary">
                        {category.points.toFixed(1)}
                        <span className="text-ink-muted">/{category.max_points}</span>
                      </span>
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-ink-muted">
                    {category.proposed_rating.toFixed(2)}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    <span className="inline-flex items-center gap-1.5">
                      {capped && (
                        <span
                          aria-hidden
                          className="h-1.5 w-1.5 rounded-full bg-serious"
                          title="Capped below the claimed rating"
                        />
                      )}
                      <span
                        className={cx(
                          capped ? "font-semibold text-ink" : "text-ink-secondary",
                        )}
                      >
                        {category.effective_rating.toFixed(2)}
                      </span>
                    </span>
                  </td>
                  <td className="py-2.5 text-xs capitalize text-ink-muted">
                    {category.best_evidence ?? "none"}
                    <span className="ml-1 tabular-nums">
                      ({category.supporting_claims})
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {adjustments.length > 0 && (
        <div className="mt-6 rounded-lg border border-hairline bg-sunken p-4">
          <h3 className="text-sm font-semibold text-ink">
            Why the score was held down
          </h3>
          <ul className="mt-2.5 space-y-2">
            {adjustments.map((adjustment, index) => (
              <li key={index} className="flex gap-2.5 text-sm leading-relaxed">
                <span
                  aria-hidden
                  className="mt-[0.55rem] h-1 w-1 shrink-0 rounded-full bg-serious"
                />
                <span className="text-ink-secondary">
                  <span className="capitalize text-ink">
                    {label(adjustment.category)}
                  </span>
                  {" — "}
                  {adjustment.text}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {score.penalties.length > 0 && (
        <div className="mt-4 rounded-lg border border-critical/30 bg-critical/5 p-4">
          <h3 className="text-sm font-semibold text-critical">
            Penalties applied
          </h3>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-secondary">
            {score.penalties.map((penalty, index) => (
              <li key={index}>{penalty}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
