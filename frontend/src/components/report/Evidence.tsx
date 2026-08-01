/**
 * Claim rendering.
 *
 * The load-bearing UI rule in this product: a sourced fact and an unsourced
 * assumption must never look alike. A founder skims and acts on whatever reads
 * as solid, so an unsourced claim gets a visible warning treatment rather than
 * a neutral one, and strength never rides on colour alone — the label is
 * always spelled out.
 */

import { safeExternalUrl, type Claim, type EvidenceStrength, type ClaimKind } from "@/lib/api";
import { Empty, cx } from "@/components/ui";

const STRENGTH_LABEL: Record<EvidenceStrength, string> = {
  strong: "Strong",
  moderate: "Moderate",
  weak: "Weak",
  anecdotal: "Anecdotal",
};

const STRENGTH_DOTS: Record<EvidenceStrength, number> = {
  strong: 3,
  moderate: 2,
  weak: 1,
  anecdotal: 0,
};

const KIND_STYLE: Record<ClaimKind, string> = {
  fact: "text-ink-secondary",
  estimate: "text-ink-secondary",
  assumption: "text-critical font-semibold",
};

const THREE_YEARS_MS = 1000 * 60 * 60 * 24 * 365 * 3;
const RENDER_EPOCH_MS = Date.now();

/** Strength as filled pips, so it is legible without relying on hue. */
function StrengthMeter({ strength }: { strength: EvidenceStrength }) {
  const filled = STRENGTH_DOTS[strength];
  return (
    <span className="inline-flex items-center gap-1" title={STRENGTH_LABEL[strength]}>
      <span aria-hidden className="flex gap-[2px]">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className={cx(
              "h-1.5 w-1.5 rounded-full",
              index < filled ? "bg-ink-secondary" : "bg-ink-muted/30",
            )}
          />
        ))}
      </span>
      <span className="text-[11px] text-ink-muted">
        {STRENGTH_LABEL[strength]}
      </span>
    </span>
  );
}

export function ClaimCard({ claim }: { claim: Claim }) {
  const sourceUrl = safeExternalUrl(claim.source_url);
  const unsourced = !sourceUrl;
  const stale =
    claim.published_date &&
    RENDER_EPOCH_MS - new Date(claim.published_date).getTime() > THREE_YEARS_MS;

  return (
    <li
      className={cx(
        "rounded-lg border px-4 py-3",
        unsourced
          ? "border-critical/30 bg-critical/5"
          : "border-hairline bg-card",
      )}
    >
      <p className="text-[15px] leading-relaxed text-ink">{claim.text}</p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs">
        <span className={cx("capitalize", KIND_STYLE[claim.kind])}>
          {claim.kind}
        </span>
        <StrengthMeter strength={claim.evidence_strength} />
        <span className="tabular-nums text-ink-muted">
          {Math.round(claim.confidence * 100)}% confidence
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="max-w-full truncate text-accent underline-offset-2 hover:underline"
          >
            {claim.source_title ?? claim.source_url}
          </a>
        ) : (
          <span className="font-medium text-critical">
            No verifiable source — treat as unconfirmed
          </span>
        )}

        {claim.published_date && (
          <span className="tabular-nums text-ink-muted">
            {claim.published_date}
          </span>
        )}
        {stale && (
          <span className="flex items-center gap-1.5 text-ink-secondary">
            <span aria-hidden className="text-serious">◆</span>
            Dated — verify before relying on it
          </span>
        )}
      </div>
    </li>
  );
}

export function ClaimList({
  claims,
  emptyMessage = "No evidence was gathered here.",
}: {
  claims: Claim[];
  emptyMessage?: string;
}) {
  if (!claims?.length) return <Empty>{emptyMessage}</Empty>;
  return (
    <ul className="space-y-2.5">
      {claims.map((claim, index) => (
        <ClaimCard key={claim.id ?? index} claim={claim} />
      ))}
    </ul>
  );
}
