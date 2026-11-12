import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Note } from "@/shared/api/types";
import { isProcessing, useNote } from "@/features/notes/hooks";
import { noteKeys } from "@/features/notes/keys";

const NOTE_ID = "00000000-0000-4000-8000-000000000001";

function note(status: Note["status"]): Note {
  return {
    id: NOTE_ID,
    status,
    source: "text",
    error_step: null,
    error_message: null,
    stalled: false,
    created_at: "2026-11-11T08:00:00Z",
  } as Note;
}

describe("isProcessing", () => {
  it("stops once the API reports the job as failed or stalled", () => {
    expect(isProcessing(note("transcribed"))).toBe(true);
    expect(isProcessing({ ...note("transcribed"), error_step: "extract" })).toBe(false);
    expect(isProcessing({ ...note("transcribed"), stalled: true })).toBe(false);
    expect(isProcessing(note("in_review"))).toBe(false);
  });
});

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } });
  // As after POST /notes/text: the 202 body is put into the cache before the page mounts.
  client.setQueryData(noteKeys.detail(NOTE_ID), note("uploaded"));
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useNote(NOTE_ID), { wrapper });
}

describe("useNote", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each(["visible", "hidden"] as const)(
    "polls a processing note until it is ready (page %s)",
    async (visibility) => {
      vi.spyOn(document, "visibilityState", "get").mockReturnValue(visibility);
      const fetchMock = vi.fn(async () => Response.json(note("in_review")));
      vi.stubGlobal("fetch", fetchMock);

      const { result } = setup();

      await waitFor(() => expect(result.current.data?.status).toBe("in_review"), {
        timeout: 3000,
      });
      expect(fetchMock).toHaveBeenCalled();
    },
  );
});
