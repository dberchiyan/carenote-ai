import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authKeys } from "@/features/auth/keys";
import { wardKeys } from "@/features/ward/keys";
import type { Note, User, WardPatient } from "@/shared/api/types";

import { DraftReview } from "./draft-review";

const NURSE = {
  id: "u1",
  username: "nurse",
  display_name: "Nora",
  role: "nurse",
  ward: "3A",
} as User;
const SMITH = { id: "p1", given_name: "John", family_name: "Smith", room: "302a" } as WardPatient;

function note(overrides: Partial<Note> = {}): Note {
  return {
    id: "n1",
    ward: "3A",
    status: "in_review",
    source: "text",
    author_id: "u1",
    patient_id: null,
    match_status: "none",
    candidates: [
      { patient_id: "p1", given_name: "John", family_name: "Smith", room: "302a", score: 80 },
    ],
    transcript: "John, 80 pulse, headache",
    transcription_model: "browser",
    draft: {
      version: 1,
      source: "ai",
      payload: {
        patient_mention: "<PATIENT_1>",
        vitals: [{ kind: "heart_rate", value: 80, unit: "/min", source_text: "80 pulse" }],
        symptoms: ["headache"],
        medications: [],
        free_text_summary: "1 vital sign value recorded; reports headache.",
        uncertain: [],
      },
      flags: { heart_rate: "normal" },
      hints: [],
      model: "rule-based-v1",
      prompt_version: "extract_v1",
      input_tokens: 10,
      output_tokens: 5,
      cost_usd: 0,
      latency_ms: 1,
      created_at: "2026-11-11T08:00:00Z",
    },
    error_step: null,
    error_message: null,
    stalled: false,
    timings_ms: {},
    created_at: "2026-11-11T08:00:00Z",
    confirmed_at: null,
    confirmed_by: null,
    ...overrides,
  };
}

function renderReview(n: Note) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(authKeys.me(), NURSE);
  client.setQueryData(wardKeys.patients(undefined), [SMITH]);
  render(
    <QueryClientProvider client={client}>
      <DraftReview note={n} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("DraftReview", () => {
  it("says only a first name was heard and keeps Confirm off until a patient is chosen", async () => {
    renderReview(note());
    expect(screen.getByText(/Only a first name was heard/)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: /^Confirm$/ });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole("radio"));
    expect(confirm).toBeEnabled();
  });

  it("blocks Confirm while a new vital has no value", async () => {
    renderReview(note({ patient_id: "p1" }));
    await userEvent.click(screen.getByRole("button", { name: "Add vital sign" }));
    expect(screen.getByRole("button", { name: /^Confirm$/ })).toBeDisabled();
    expect(screen.getByText(/Enter a value for every vital sign/)).toBeInTheDocument();
  });

  it("saves the edited draft before confirming, and not when the save fails", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        const method = init?.method ?? (input instanceof Request ? input.method : "GET");
        const path = new URL(url).pathname;
        if (method === "GET") {
          // Background refetches of the cached queries must not overwrite the fixtures.
          return Response.json(path === "/api/auth/me" ? NURSE : [SMITH]);
        }
        calls.push(`${method} ${path}`);
        if (method === "PATCH") {
          return Response.json(
            {
              code: "conflict",
              message: "The draft changed while you were editing. Reload it.",
              details: {},
            },
            { status: 409 },
          );
        }
        return Response.json(note({ patient_id: "p1", status: "confirmed" }));
      }),
    );
    renderReview(note({ patient_id: "p1" }));
    await userEvent.click(screen.getByRole("button", { name: "Remove symptom headache" }));
    await userEvent.click(screen.getByRole("button", { name: /^Confirm$/ }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/changed while you were editing/),
    );
    expect(calls).toEqual(["PATCH /api/notes/n1/draft"]); // the failed save stops the confirm
  });
});
