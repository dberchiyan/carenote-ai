import { describe, expect, it } from "vitest";

import { highlightSegments } from "@/features/notes/lib/highlight";

describe("highlightSegments", () => {
  const transcript = "Mrs. Keller, BP 150/90, pulse 88. Gave paracetamol.";

  it("marks each span once, in transcript order", () => {
    const segments = highlightSegments(transcript, [
      { fieldId: "hr", text: "pulse 88" },
      { fieldId: "bp", text: "bp 150/90" },
    ]);
    expect(segments.filter((s) => s.fieldId).map((s) => [s.fieldId, s.text])).toEqual([
      ["bp", "BP 150/90"],
      ["hr", "pulse 88"],
    ]);
    expect(segments.map((s) => s.text).join("")).toBe(transcript);
  });

  it("lets two fields share a span without duplicating text", () => {
    const segments = highlightSegments(transcript, [
      { fieldId: "sys", text: "BP 150/90" },
      { fieldId: "dia", text: "BP 150/90" },
    ]);
    expect(segments.filter((s) => s.fieldId)).toHaveLength(1);
    expect(segments.map((s) => s.text).join("")).toBe(transcript);
  });

  it("ignores spans that are not in the transcript", () => {
    expect(highlightSegments(transcript, [{ fieldId: "x", text: "temp 39" }])).toEqual([
      { text: transcript, fieldId: null },
    ]);
  });
});
