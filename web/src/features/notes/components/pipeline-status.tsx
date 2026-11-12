import type { Note } from "@/shared/api/types";

const STEPS = [
  { key: "uploaded", label: "Uploaded" },
  { key: "transcribed", label: "Transcribed" },
  { key: "in_review", label: "Ready for review" },
] as const;

const ORDER = ["uploaded", "transcribed", "in_review", "confirmed", "rejected"];

export function PipelineStatus({ note }: { note: Note }) {
  const reached = ORDER.indexOf(note.status);
  const steps = note.source === "text" ? STEPS.filter((s) => s.key !== "uploaded") : STEPS;
  return (
    <ol
      className="border-line bg-surface shadow-card flex flex-wrap items-center gap-2 rounded-2xl border p-2 text-sm"
      aria-label="Processing steps"
    >
      {steps.map((step, i) => {
        const done = ORDER.indexOf(step.key) <= reached;
        const current = !done && ORDER.indexOf(step.key) === reached + 1;
        const failed = current && note.error_step !== null;
        return (
          <li key={step.key} className="flex items-center gap-2">
            {i > 0 && (
              <span
                aria-hidden="true"
                className={`h-px w-6 ${done ? "bg-brand/50" : "bg-line-strong"}`}
              />
            )}
            <span
              aria-current={current ? "step" : undefined}
              className={`inline-flex items-center gap-2 rounded-xl px-3 py-1.5 font-medium ${
                failed
                  ? "bg-red-50 text-red-900 dark:bg-red-950/60 dark:text-red-100"
                  : done
                    ? "text-ink"
                    : current
                      ? "bg-surface-3 text-ink"
                      : "text-ink-3"
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex size-5 items-center justify-center rounded-full text-[11px] font-bold ${
                  failed
                    ? "bg-red-600 text-white"
                    : done
                      ? "bg-brand text-brand-fg"
                      : "ring-line-strong ring-1 ring-inset"
                }`}
              >
                {failed ? "✕" : done ? "✓" : current ? <Spinner /> : ""}
              </span>
              {step.label}
              {failed && <span className="sr-only"> (failed)</span>}
              {done && <span className="sr-only"> (done)</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function Spinner() {
  return (
    <span className="inline-block size-2.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none" />
  );
}
