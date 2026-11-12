import { describe, expect, it } from "vitest";

import { linear, niceTicks } from "@/shared/lib/scale";

describe("niceTicks", () => {
  it("covers the domain with round steps", () => {
    const ticks = niceTicks(87, 168);
    expect(ticks[0]).toBeLessThanOrEqual(87);
    expect(ticks.at(-1)).toBeGreaterThanOrEqual(168);
    expect(ticks).toEqual([80, 100, 120, 140, 160, 180]);
  });

  it("handles a flat series", () => {
    expect(niceTicks(37, 37).length).toBeGreaterThan(1);
  });
});

describe("linear", () => {
  it("maps domain to range", () => {
    expect(linear([0, 10], [100, 0])(5)).toBe(50);
  });
});
