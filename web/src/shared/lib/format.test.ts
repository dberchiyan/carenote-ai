import { describe, expect, it } from "vitest";

import { ageFrom, formatDateTime, formatRelative } from "@/shared/lib/format";

describe("ageFrom", () => {
  it("counts full years only", () => {
    expect(ageFrom("1944-08-04", new Date("2026-08-03"))).toBe(81);
    expect(ageFrom("1944-08-04", new Date("2026-08-04"))).toBe(82);
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-11-11T18:00:00");
  const at = (iso: string) => formatRelative(iso, now);

  it("uses words for the recent past", () => {
    expect(at("2026-11-11T17:59:40")).toBe("just now");
    expect(at("2026-11-11T17:55:00")).toBe("5 min ago");
    expect(at("2026-11-11T15:00:00")).toBe("3 h ago");
  });

  it("names today and yesterday with the time", () => {
    expect(at("2026-11-11T08:04:00")).toMatch(/^Today, /);
    expect(at("2026-11-10T17:04:00")).toMatch(/^Yesterday, /);
  });

  it("falls back to the full date further back", () => {
    expect(at("2026-11-05T17:04:00")).toBe(formatDateTime("2026-11-05T17:04:00"));
  });
});
