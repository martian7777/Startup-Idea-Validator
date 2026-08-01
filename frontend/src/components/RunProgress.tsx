"use client";

/**
 * Pipeline progress.
 *
 * The three research stages run concurrently, so they are visually grouped
 * rather than listed as a sequence — showing them as consecutive steps would
 * misrepresent how the graph executes.
 */

import { STAGES } from "@/lib/api";
import type { StageState } from "@/hooks/useRunStream";
import { Card, cx } from "@/components/ui";

function Marker({ state }: { state: StageState }) {
  if (state === "done") {
    return (
      <span
        aria-hidden
        className="flex h-4 w-4 items-center justify-center rounded-full bg-good/15 text-[9px] text-good"
      >
        ✓
      </span>
    );
  }
  if (state === "failed") {
    return (
      <span
        aria-hidden
        className="flex h-4 w-4 items-center justify-center rounded-full bg-critical/15 text-[9px] text-critical"
      >
        ✕
      </span>
    );
  }
  if (state === "running") {
    return (
      <span aria-hidden className="relative flex h-4 w-4 items-center justify-center">
        <span className="absolute h-4 w-4 animate-ping rounded-full bg-accent/25" />
        <span className="h-2 w-2 rounded-full bg-accent" />
      </span>
    );
  }
  return (
    <span
      aria-hidden
      className="flex h-4 w-4 items-center justify-center"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-ink-muted/40" />
    </span>
  );
}

const STATE_TEXT: Record<StageState, string> = {
  pending: "Waiting",
  running: "In progress",
  done: "Done",
  failed: "Failed",
};

function Row({ label, state }: { label: string; state: StageState }) {
  return (
    <li className="flex items-center gap-3 py-2">
      <Marker state={state} />
      <span
        className={cx(
          "flex-1 text-sm",
          state === "pending" ? "text-ink-muted" : "text-ink",
        )}
      >
        {label}
      </span>
      {/* State is spelled out, never carried by the marker colour alone. */}
      <span className="text-[11px] uppercase tracking-wide text-ink-muted">
        {STATE_TEXT[state]}
      </span>
    </li>
  );
}

export function RunProgress({
  stageStates,
}: {
  stageStates: Record<string, StageState>;
}) {
  const sequential = STAGES.filter((stage) => !stage.parallel);
  const parallel = STAGES.filter((stage) => stage.parallel);

  const first = sequential.slice(0, 1);
  const rest = sequential.slice(1);

  const done = Object.values(stageStates).filter((s) => s === "done").length;
  const progress = done / STAGES.length;

  return (
    <Card>
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold text-ink">Pipeline</h2>
        <span className="tabular-nums text-xs text-ink-muted">
          {done} of {STAGES.length} complete
        </span>
      </div>

      <span className="mt-3 flex h-1 w-full overflow-hidden rounded-full bg-ink-muted/15">
        <span
          className="h-full rounded-full bg-accent transition-[width] duration-500"
          style={{ width: `${progress * 100}%` }}
        />
      </span>

      <ul className="mt-3 divide-y divide-hairline">
        {first.map((stage) => (
          <Row
            key={stage.node}
            label={stage.label}
            state={stageStates[stage.node] ?? "pending"}
          />
        ))}
      </ul>

      <div className="my-2 rounded-lg border border-dashed border-hairline px-3 py-1">
        <p className="py-1 text-[11px] uppercase tracking-wide text-ink-muted">
          Running in parallel
        </p>
        <ul className="divide-y divide-hairline">
          {parallel.map((stage) => (
            <Row
              key={stage.node}
              label={stage.label}
              state={stageStates[stage.node] ?? "pending"}
            />
          ))}
        </ul>
      </div>

      <ul className="divide-y divide-hairline">
        {rest.map((stage) => (
          <Row
            key={stage.node}
            label={stage.label}
            state={stageStates[stage.node] ?? "pending"}
          />
        ))}
      </ul>
    </Card>
  );
}
