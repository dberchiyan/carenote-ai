"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * Filter state that lives in the URL (`?q=keller&flagged=1`), so a filtered view can be
 * reloaded, shared and returned to with Back. Values are strings; empty removes the key.
 */
export function useUrlState(): [
  URLSearchParams,
  (changes: Record<string, string | number | null | undefined>) => void,
] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const set = useCallback(
    (changes: Record<string, string | number | null | undefined>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(changes)) {
        if (value === null || value === undefined || value === "" || value === 0) next.delete(key);
        else next.set(key, String(value));
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, router, pathname],
  );
  return [params, set];
}
