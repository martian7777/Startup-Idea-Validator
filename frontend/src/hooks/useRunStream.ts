"use client";

/**
 * Subscribes to a run's SSE stream and derives view state from it.
 *
 * The backend replays its durable event log before tailing, so this hook holds
 * no persistence of its own — a refresh mid-run rebuilds the same state from
 * the replay. Events are keyed by `seq` because a reconnect can redeliver.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  STAGES,
  type OpportunityReport,
  type OpportunityScore,
  type ProgressEvent,
  type RunStatus,
} from "@/lib/api";

export type StageState = "pending" | "running" | "done" | "failed";

export interface RunStream {
  events: ProgressEvent[];
  stageStates: Record<string, StageState>;
  status: RunStatus;
  score: OpportunityScore | null;
  report: OpportunityReport | null;
  markdown: string | null;
  error: string | null;
  unverifiedCitations: number;
  isFinished: boolean;
}

export function useRunStream(runId: string): RunStream {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [status, setStatus] = useState<RunStatus>("queued");
  const [score, setScore] = useState<OpportunityScore | null>(null);
  const [report, setReport] = useState<OpportunityReport | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seenSeqs = useRef<Set<number>>(new Set());

  useEffect(() => {
    seenSeqs.current = new Set();
    const source = new EventSource(api.streamUrl(runId));

    const loadResult = async () => {
      try {
        const run = await api.getRun(runId);
        setStatus(run.status);
        if (run.error) setError(run.error);
      } catch {
        /* the report fetch below carries the useful signal */
      }
      try {
        const result = await api.getReport(runId);
        setScore(result.score);
        setReport(result.content as unknown as OpportunityReport);
        setMarkdown(result.markdown);
      } catch {
        /* a failed run legitimately has no report */
      }
    };

    source.addEventListener("progress", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as ProgressEvent;
      if (seenSeqs.current.has(parsed.seq)) return;
      seenSeqs.current.add(parsed.seq);

      setEvents((previous) => [...previous, parsed]);
      if (parsed.phase === "failed" && parsed.payload?.error) {
        setError(String(parsed.payload.error));
      }
    });

    source.addEventListener("done", () => {
      source.close();
      void loadResult();
    });

    source.onerror = () => source.close();
    return () => source.close();
  }, [runId]);

  const stageStates = useMemo(() => {
    const states: Record<string, StageState> = {};
    for (const { node } of STAGES) states[node] = "pending";

    for (const event of events) {
      // An extract node completing means its whole research branch is done, so
      // credit the search stage the UI actually shows.
      const node = event.node.replace(/_extract$/, "_search");
      if (!(node in states)) continue;

      if (event.phase === "started" && states[node] === "pending") {
        states[node] = "running";
      }
      if (event.phase === "completed") states[node] = "done";
      if (event.phase === "failed") states[node] = "failed";
    }
    return states;
  }, [events]);

  const unverifiedCitations = useMemo(() => {
    const event = events.find((e) => e.phase === "attribution_failed");
    return event ? Number(event.payload?.count ?? 0) : 0;
  }, [events]);

  return {
    events,
    stageStates,
    status,
    score,
    report,
    markdown,
    error,
    unverifiedCitations,
    isFinished: score !== null || status === "failed" || status === "interrupted",
  };
}
