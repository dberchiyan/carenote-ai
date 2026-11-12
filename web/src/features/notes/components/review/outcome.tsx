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
        className="shadow-card border-ok-line bg-ok-soft text-ok-fg flex flex-wrap items-center gap-4 rounded-2xl border p-5"
      >
        <span className="bg-ok-soft text-ok ring-ok-line flex size-10 shrink-0 items-center justify-center rounded-full ring-1">
          <CheckIcon size={20} />
        </span>
        <p className="flex-1 font-semibold">
          <span aria-hidden="true">✓ </span>Confirmed{" "}
          {note.confirmed_at ? formatDateTime(note.confirmed_at) : ""}
          <span className="text-ok-fg block text-sm font-normal">
            Saved to the patient record and the audit log.
          </span>
        </p>
        {note.patient_id && (
          <Link
            href={`/patients/${note.patient_id}`}
            className="bg-surface text-ok-fg ring-ok-line hover:bg-ok-soft focus-visible:outline-ok inline-flex items-center gap-1 rounded-xl px-3.5 py-2 text-sm font-semibold ring-1 focus-visible:outline-2"
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
