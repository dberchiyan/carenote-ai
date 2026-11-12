import { describe, expect, it } from "vitest";

import { frameRms, micError, SILENCE_RMS } from "@/features/notes/components/recorder";

describe("frameRms", () => {
  it("is zero for the all-zero stream a browser without mic permission delivers", () => {
    expect(frameRms(new Float32Array(1024))).toBe(0);
  });

  it("puts quiet speech well above the silence threshold", () => {
    const speech = Float32Array.from({ length: 1024 }, (_, i) => 0.05 * Math.sin(i / 8));
    expect(frameRms(speech)).toBeGreaterThan(SILENCE_RMS * 5);
  });
});

describe("micError", () => {
  const error = (name: string) => new DOMException("x", name);

  it("tells the nurse how to unblock a microphone the browser has blocked", () => {
    const message = micError(error("NotAllowedError"));
    expect(message).toMatch(/blocked/i);
    expect(message).toMatch(/address bar/i);
  });

  it("names the other common failures", () => {
    expect(micError(error("NotFoundError"))).toMatch(/no microphone/i);
    expect(micError(error("NotReadableError"))).toMatch(/another app/i);
  });

  it("falls back to a generic message", () => {
    expect(micError(new Error("boom"))).toMatch(/upload a file/i);
  });
});
