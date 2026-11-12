import { describe, expect, it } from "vitest";

import {
  formatVital,
  handoverText,
  mergeBloodPressure,
  needsAttention,
  trend,
  type Handover,
  type VitalChip,
  type VitalFact,
} from "./text";

const vital = (value: number, previous: number | null): VitalFact =>
  ({ value, previous, kind: "spo2", label: "SpO₂", unit: "%", flag: "normal" }) as VitalFact;

describe("trend", () => {
  it("compares with the last value before the shift", () => {
    expect(trend(vital(88, 96))).toBe("down");
    expect(trend(vital(150, 128))).toBe("up");
    expect(trend(vital(96, 96))).toBeNull();
    expect(trend(vital(96, null))).toBeNull();
  });
});

describe("handoverText", () => {
  it("reads as a handover sheet: ward summary, then each room in priority order", () => {
    const h = {
      ward: "3A",
      hours: 12,
      summary: "2 patients on ward 3A.",
      patients: [
        {
          room: "301a",
          given_name: "Anna",
          family_name: "Keller",
          priority: "critical",
          summary: "SpO₂ 88% (critical).",
        },
        {
          room: "302a",
          given_name: "John",
          family_name: "Smith",
          priority: "stable",
          summary: "Stable.",
        },
      ],
    } as unknown as Handover;
    const text = handoverText(h, new Date("2026-11-12T19:00:00Z"));
    expect(text.split("\n")[0]).toMatch(/^Ward 3A handover · last 12 h · /);
    expect(text).toContain("Room 301a · Keller, Anna (critical)\nSpO₂ 88% (critical).");
    expect(text.indexOf("301a")).toBeLessThan(text.indexOf("302a"));
  });
});

describe("mergeBloodPressure", () => {
  const bp = (kind: string, value: number, flag: VitalFact["flag"], previous: number | null) =>
    ({ kind, value, flag, previous, label: kind, unit: "mmHg", worst_in_shift: flag }) as VitalFact;

  it("joins systolic and diastolic into one reading flagged by the worse one", () => {
    const merged = mergeBloodPressure([
      vital(97, 96),
      bp("systolic_bp", 128, "normal", 120),
      bp("diastolic_bp", 102, "warning", 80),
    ]);
    expect(merged.map((v) => v.kind)).toEqual(["spo2", "bp"]);
    const merged1 = merged[1];
    expect(merged1?.flag).toBe("warning");
    expect(merged1?.previous).toBe(120);
    expect(formatVital(merged1 as VitalChip)).toBe("128/102 mmHg");
  });

  it("leaves a lone systolic alone", () => {
    const only = [bp("systolic_bp", 150, "warning", null)];
    expect(mergeBloodPressure(only)).toEqual(only);
  });
});

describe("formatVital", () => {
  it("keeps % and °C tight and spaces other units", () => {
    expect(formatVital(vital(91, null))).toBe("91%");
    expect(formatVital({ ...vital(37.2, null), unit: "°C" })).toBe("37.2°C");
    expect(formatVital({ ...vital(16, null), unit: "/min" })).toBe("16 /min");
  });
});

describe("needsAttention", () => {
  it("includes a value that was flagged earlier in the shift", () => {
    expect(needsAttention({ ...vital(96, 88), worst_in_shift: "critical" })).toBe(true);
    expect(needsAttention({ ...vital(96, 95), worst_in_shift: "normal" })).toBe(false);
  });
});
