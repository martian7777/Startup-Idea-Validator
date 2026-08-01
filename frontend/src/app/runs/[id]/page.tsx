"use client";

/** Live run view: progress while researching, full report once scored. */

import { use, useState } from "react";
import Link from "next/link";
import { useRunStream } from "@/hooks/useRunStream";
import { Callout, Card, cx } from "@/components/ui";
import { RunProgress } from "@/components/RunProgress";
import { Report, REPORT_SECTIONS } from "@/components/report/Report";

function DownloadButton({ markdown, runId }: { markdown: string; runId: string }) {
  const [href, setHref] = useState<string | null>(null);

  // The object URL is created on demand so it is not leaked on every render.
  const prepare = () => {
    if (href) URL.revokeObjectURL(href);
    setHref(URL.createObjectURL(new Blob([markdown], { type: "text/markdown" })));
  };

  return (
    <a
      href={href ?? "#"}
      onMouseEnter={prepare}
      onFocus={prepare}
      onClick={(event) => {
        if (!href) {
          event.preventDefault();
          prepare();
        }
      }}
      download={`validation-report-${runId.slice(0, 8)}.md`}
      className="rounded-lg border border-hairline bg-card px-3 py-1.5 text-sm text-ink transition-colors hover:bg-sunken"
    >
      Download report
    </a>
  );
}

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const {
    stageStates,
    score,
    report,
    markdown,
    error,
    unverifiedCitations,
    isFinished,
  } = useRunStream(id);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-hairline bg-page/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-3">
          <Link
            href="/"
            className="text-sm text-ink-secondary transition-colors hover:text-ink"
          >
            ← New idea
          </Link>
          <span className="ml-auto flex items-center gap-3">
            {markdown && <DownloadButton markdown={markdown} runId={id} />}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          {isFinished ? "Validation report" : "Researching your idea"}
        </h1>
        {!isFinished && (
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-secondary">
            Three research agents run in parallel, then their findings are
            challenged before anything is scored. This takes a few minutes.
          </p>
        )}

        <div className="mt-8 space-y-6">
          {!isFinished && <RunProgress stageStates={stageStates} />}

          {unverifiedCitations > 0 && (
            <Callout tone="warn" title="Unverifiable citations were removed">
              {unverifiedCitations} citation
              {unverifiedCitations === 1 ? " was" : "s were"} not found in what
              search actually retrieved. Those claims were stripped of their
              sources and downgraded, which lowers the score rather than
              flattering it.
            </Callout>
          )}

          {error && (
            <Card className="border-critical/30 bg-critical/5">
              <h2 className="text-sm font-semibold text-critical">
                This run did not finish
              </h2>
              <p className="mt-1.5 break-words text-sm leading-relaxed text-ink-secondary">
                {error}
              </p>
            </Card>
          )}

          {score && (
            <div className="lg:flex lg:gap-10">
              {/* Section rail: 16 sections need a spine to be navigable. */}
              <nav className="hidden shrink-0 lg:block lg:w-44">
                <ul className="sticky top-20 space-y-1 border-l border-hairline">
                  {REPORT_SECTIONS.map((section, index) => (
                    <li key={section.id}>
                      <a
                        href={`#${section.id}`}
                        className={cx(
                          "-ml-px flex gap-2 border-l border-transparent py-1 pl-3 text-xs",
                          "text-ink-muted transition-colors hover:border-accent hover:text-ink",
                        )}
                      >
                        <span className="font-mono tabular-nums opacity-60">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        {section.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>

              <div className="min-w-0 flex-1">
                <Report report={report} score={score} />
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
