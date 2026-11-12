import { describe, expect, it } from "vitest";

import { clusterReadings, type Reading } from "./chart-cluster";

const r = (x: number, value: number, flag: Reading["flag"] = "normal"): Reading => ({
  at: `2026-11-12T10:${String(x).padStart(2, "0")}:00Z`,
  value,
  flag,
  x,
});

describe("clusterReadings", () => {
  it("keeps readings that are far enough apart as separate points", () => {
    const out = clusterReadings([r(0, 110), r(40, 115), r(80, 120)], 18);
    expect(out.map((c) => c.readings.length)).toEqual([1, 1, 1]);
  });

  it("merges readings drawn too close together, plotting the latest with the worst flag", () => {
    const out = clusterReadings(
      [r(0, 110), r(500, 150, "warning"), r(505, 168, "warning"), r(510, 120, "normal")],
      18,
    );
    expect(out).toHaveLength(2);
    const merged = out[1];
    expect(merged?.readings.map((x) => x.value)).toEqual([150, 168, 120]);
    expect(merged?.value).toBe(120); // the latest reading
    expect(merged?.x).toBe(510);
    expect(merged?.flag).toBe("warning"); // never hidden by a later normal value
  });

  it("measures the gap from the first reading of a group, so a slow drift still splits", () => {
    const out = clusterReadings([r(0, 1), r(10, 2), r(20, 3), r(30, 4)], 18);
    expect(out.map((c) => c.readings.length)).toEqual([2, 2]);
  });
});
