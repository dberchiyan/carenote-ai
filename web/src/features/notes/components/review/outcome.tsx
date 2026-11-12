import Link from "next/link";

import type { Draft, Note } from "@/shared/api/types";
import { formatDateTime } from "@/shared/lib/format";
import { CheckIcon, ChevronRightIcon } from "@/shared/ui/icons";

/** Which version this is, what produced it and what it cost. */
export function DraftMeta({ draft }: { draft: Draft }) {
  return (
    <p className="text-ink-3 flex flex-wrap items-center gap-x-2 gap-y-1 px-1 font-mono text-[11px]">
      <span className="font-sans font-semibold">
        {draft.source === "ai" ? "AI draft" : "Edited by nurse"} v{draft.version}
      </span>
      <span aria-hidden="true">·</span>
      <span>{draft.model ?? "—"}</span>
      <span aria-hidden="true">·</span>
      <span>prompt {draft.prompt_version ?? "—"}</span>
      <span aria-hidden="true">·</span>
      <span>
        {draft.input_tokens} in / {draft.output_tokens} out tokens
      </span>
      <span aria-hidden="true">·</span>
      <span>${draft.cost_usd.toFixed(4)}</span>
      <span aria-hidden="true">·</span>
      <span>{draft.latency_ms} ms</span>
    </p>
  );
}

/** The final state of a reviewed note, confirmed or rejected. */
export function OutcomeBanner({ note }: { note: Note }) {
  if (note.status === "confirmed") {
    return (
      <div
        role="status"
        className="shadow-card flex flex-wrap items-center gap-4 rounded-2xl border border-emerald-300 bg-emerald-50 p-5 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-950/40 dark:text-emerald-50"
      >
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
          <CheckIcon size={20} />
        </span>
        <p className="flex-1 font-semibold">
          <span aria-hidden="true">✓ </span>Confirmed{" "}
          {note.confirmed_at ? formatDateTime(note.confirmed_at) : ""}
          <span className="block text-sm font-normal text-emerald-900 dark:text-emerald-200">
            Saved to the patient record and the audit log.
          </span>
        </p>
        {note.patient_id && (
          <Link
            href={`/patients/${note.patient_id}`}
            className="inline-flex items-center gap-1 rounded-xl bg-white px-3.5 py-2 text-sm font-semibold text-emerald-900 ring-1 ring-emerald-300 hover:bg-emerald-100 focus-visible:outline-2 focus-visible:outline-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-50 dark:ring-emerald-500/40"
          >
            Open patient record
            <ChevronRightIcon size={15} />
          </Link>
        )}
      </div>
    );
  }
  if (note.status === "rejected") {
    return (
      <div role="status" className="card p-5">
        <p className="font-semibold">Rejected — nothing was saved to the patient record.</p>
      </div>
    );
  }
  return null;
}
