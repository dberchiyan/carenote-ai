import type { components } from "@/shared/api/schema";

export type Handover = components["schemas"]["HandoverOut"];
export type HandoverPatient = components["schemas"]["HandoverPatientOut"];
export type VitalFact = components["schemas"]["VitalFact"];

const PRIORITY_LABEL: Record<HandoverPatient["priority"], string> = {
  critical: "critical",
  warning: "warning",
  review: "awaiting review",
  stable: "stable",
};

/** The handover as plain text, for pasting into a message or the ward's handover sheet. */
export function handoverText(h: Handover, now: Date = new Date()): string {
  const when = now.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  const lines = [`Ward ${h.ward} handover · last ${h.hours} h · ${when}`, "", h.summary, ""];
  for (const p of h.patients) {
    lines.push(
      `Room ${p.room} · ${p.family_name}, ${p.given_name} (${PRIORITY_LABEL[p.priority]})`,
    );
    lines.push(p.summary, "");
  }
  lines.push("Synthetic demo data. Built from nurse-confirmed values only.");
  return lines.join("\n");
}

/** ↑ or ↓ against the last value before the shift; nothing for a first reading or no change. */
export function trend(v: VitalFact): "up" | "down" | null {
  if (v.previous == null || v.previous === v.value) return null;
  return v.value > v.previous ? "up" : "down";
}

export type VitalChip = VitalFact & { display?: string };

const RANK = { normal: 0, warning: 1, critical: 2 } as const;

/** Systolic and diastolic as one chip, "BP 168/96", flagged by the worse of the two. */
export function mergeBloodPressure(vitals: VitalFact[]): VitalChip[] {
  const sys = vitals.find((v) => v.kind === "systolic_bp");
  const dia = vitals.find((v) => v.kind === "diastolic_bp");
  if (!sys || !dia) return vitals;
  const worse = RANK[dia.flag] > RANK[sys.flag] ? dia : sys;
  const bp: VitalChip = {
    ...worse,
    kind: "bp",
    label: "BP",
    value: sys.value,
    previous: sys.previous,
    display: `${sys.value}/${dia.value}`,
  };
  return vitals.flatMap((v) =>
    v.kind === "systolic_bp" ? [bp] : v.kind === "diastolic_bp" ? [] : [v],
  );
}

/** The value with its unit the way it is read aloud: "91%", "37.2°C", "168/96 mmHg". */
export function formatVital(v: VitalChip): string {
  const unit = v.unit === "%" || v.unit === "°C" ? v.unit : ` ${v.unit}`;
  return `${v.display ?? v.value}${unit}`;
}

/** Needs a tile: flagged now, or flagged at some point this shift. */
export function needsAttention(v: VitalFact): boolean {
  return v.flag !== "normal" || v.worst_in_shift !== "normal";
}
