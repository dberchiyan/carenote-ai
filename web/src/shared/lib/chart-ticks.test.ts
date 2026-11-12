import { describe, expect, it } from "vitest";

import { xTickIndices } from "@/shared/lib/chart-ticks";

const day = (d: number, h = 8) => new Date(2026, 10, d, h).getTime();

describe("xTickIndices", () => {
  it("labels each day once even when many readings share the day", () => {
    const times = [day(10, 8), day(10, 12), day(11, 8), day(11, 9), day(11, 10), day(11, 17)];
    const xs = [0, 100, 200, 300, 400, 500];
    expect(xTickIndices(times, xs)).toEqual([0, 2]);
  });

  it("drops a label that would overlap the previous one", () => {
    const times = [day(10), day(11), day(12)];
    const xs = [0, 20, 200];
    expect(xTickIndices(times, xs, { minGap: 56 })).toEqual([0, 2]);
  });

  it("samples evenly when there are more days than labels", () => {
    const times = Array.from({ length: 9 }, (_, i) => day(1 + i));
    const xs = times.map((_, i) => i * 100);
    expect(xTickIndices(times, xs, { max: 3 })).toEqual([0, 4, 8]);
  });

  it("handles a single reading", () => {
    expect(xTickIndices([day(1)], [250])).toEqual([0]);
    expect(xTickIndices([], [])).toEqual([]);
  });
});
