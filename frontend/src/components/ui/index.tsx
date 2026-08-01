/** Layout and text primitives shared across the app. */

import type { ReactNode } from "react";

export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Card({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border border-hairline bg-card",
        padded && "p-5 sm:p-6",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** A numbered report section. The number gives the 16 sections a spine. */
export function Section({
  index,
  title,
  subtitle,
  children,
  id,
}: {
  index: number;
  title: string;
  subtitle?: string;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section id={id} className="scroll-mt-20">
      <header className="mb-4 flex items-baseline gap-3">
        <span className="font-mono text-xs tabular-nums text-ink-muted">
          {String(index).padStart(2, "0")}
        </span>
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-ink">
            {title}
          </h2>
          {subtitle && (
            <p className="mt-0.5 text-sm text-ink-secondary">{subtitle}</p>
          )}
        </div>
      </header>
      {children}
    </section>
  );
}

export function Prose({ children }: { children: ReactNode }) {
  return (
    <p className="text-[15px] leading-relaxed text-ink-secondary whitespace-pre-line">
      {children}
    </p>
  );
}

export function BulletList({
  items,
  tone = "neutral",
}: {
  items: string[];
  tone?: "neutral" | "risk";
}) {
  if (!items?.length) {
    return <Empty>Nothing recorded for this section.</Empty>;
  }
  return (
    <ul className="space-y-2.5">
      {items.map((item, index) => (
        <li key={index} className="flex gap-3 text-[15px] leading-relaxed">
          <span
            aria-hidden
            className={cx(
              "mt-[0.55rem] h-1 w-1 shrink-0 rounded-full",
              tone === "risk" ? "bg-critical" : "bg-ink-muted",
            )}
          />
          <span className="text-ink-secondary">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-hairline px-4 py-3 text-sm text-ink-muted">
      {children}
    </p>
  );
}

/**
 * Callout for the things a founder must not skim past. `warn` is used where
 * the system is telling them its own output is weak.
 */
export function Callout({
  tone = "warn",
  title,
  children,
}: {
  tone?: "warn" | "critical" | "neutral";
  title?: string;
  children: ReactNode;
}) {
  const accent = {
    warn: "border-l-warning",
    critical: "border-l-critical",
    neutral: "border-l-axis",
  }[tone];

  return (
    <div
      className={cx(
        "rounded-r-lg border border-l-2 border-hairline bg-sunken px-4 py-3",
        accent,
      )}
    >
      {title && (
        <p className="text-sm font-semibold text-ink">{title}</p>
      )}
      <div className="text-sm leading-relaxed text-ink-secondary">
        {children}
      </div>
    </div>
  );
}

/**
 * Stat tile. Proportional figures on the value by design — tabular-nums makes
 * a number like 121 look loose at display size.
 */
export function StatTile({
  label,
  value,
  unit,
  footnote,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  footnote?: string;
  tone?: "default" | "muted";
}) {
  return (
    <div className="rounded-lg border border-hairline bg-card px-4 py-3.5">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
        {label}
      </p>
      <p
        className={cx(
          "mt-1.5 text-2xl font-semibold leading-none",
          tone === "muted" ? "text-ink-secondary" : "text-ink",
        )}
      >
        {value}
        {unit && (
          <span className="ml-1 text-sm font-normal text-ink-muted">
            {unit}
          </span>
        )}
      </p>
      {footnote && (
        <p className="mt-1.5 text-xs leading-snug text-ink-muted">{footnote}</p>
      )}
    </div>
  );
}
