import type { Flag } from "@/shared/api/types";
import { FLAG_META } from "@/shared/lib/vitals";

/** Flag shown with an icon and a word, never colour alone. */
export function FlagBadge({ flag, compact = false }: { flag: Flag; compact?: boolean }) {
  const meta = FLAG_META[flag];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset ${meta.className}`}
    >
      <span aria-hidden="true">{meta.icon}</span>
      {compact ? <span className="sr-only">{meta.label}</span> : meta.label}
    </span>
  );
}
