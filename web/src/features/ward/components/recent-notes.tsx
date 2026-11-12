import Link from "next/link";

import type { NoteSummary } from "@/shared/api/types";
import { formatDateTime } from "@/shared/lib/format";
import { ChevronRightIcon, FileIcon } from "@/shared/ui/icons";
import { Pill } from "@/shared/ui/states";

const STATUS_LABELS: Record<NoteSummary["status"], string> = {
  uploaded: "Processing",
  transcribed: "Processing",
  in_review: "Needs review",
  confirmed: "Confirmed",
  rejected: "Rejected",
};

export function NoteItem({ n, name }: { n: NoteSummary; name: string }) {
  const tone = n.error_step
    ? "danger"
    : n.status === "in_review"
      ? "info"
      : n.status === "confirmed"
        ? "success"
        : "neutral";
  return (
    <li>
      <Link
        href={`/notes/${n.id}`}
        className="group hover:bg-surface-2 focus-visible:outline-brand-ring flex items-center gap-3 rounded-xl px-3 py-3 transition-colors focus-visible:outline-2"
      >
        <span className="bg-surface-3 text-ink-2 flex size-9 shrink-0 items-center justify-center rounded-lg">
          <FileIcon size={16} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="text-ink block truncate text-sm font-semibold">{name}</span>
          <span className="text-ink-3 block truncate text-xs">{formatDateTime(n.created_at)}</span>
        </span>
        <Pill tone={tone}>{n.error_step ? "Failed — retry" : STATUS_LABELS[n.status]}</Pill>
        <ChevronRightIcon
          size={16}
          className="text-ink-3 shrink-0 transition-transform group-hover:translate-x-0.5"
        />
      </Link>
    </li>
  );
}
