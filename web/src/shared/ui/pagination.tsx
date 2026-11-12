import { Button } from "@/shared/ui/button";

export type PageInfo = { total: number; limit: number; offset: number };

/** "1–100 of 342" with previous/next. Pages are offset-based, matching the API's `Page`. */
export function Pagination({
  page,
  onOffset,
  label = "items",
}: {
  page: PageInfo;
  onOffset: (offset: number) => void;
  label?: string;
}) {
  if (page.total <= page.limit && page.offset === 0) return null;
  const first = page.total === 0 ? 0 : page.offset + 1;
  const last = Math.min(page.offset + page.limit, page.total);
  return (
    <nav
      aria-label="Pagination"
      className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm"
    >
      <p className="text-ink-2 tabular-nums" aria-live="polite">
        {first}–{last} of {page.total} {label}
      </p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={page.offset === 0}
          onClick={() => onOffset(Math.max(0, page.offset - page.limit))}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={last >= page.total}
          onClick={() => onOffset(page.offset + page.limit)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
