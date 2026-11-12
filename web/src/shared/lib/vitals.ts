import type { Flag, VitalKind } from "@/shared/api/types";

export const VITAL_KINDS: VitalKind[] = [
  "systolic_bp",
  "diastolic_bp",
  "heart_rate",
  "respiratory_rate",
  "temperature",
  "spo2",
  "weight",
  "blood_glucose",
];

export const VITAL_LABELS: Record<VitalKind, { label: string; short: string; unit: string }> = {
  systolic_bp: { label: "Systolic BP", short: "SYS", unit: "mmHg" },
  diastolic_bp: { label: "Diastolic BP", short: "DIA", unit: "mmHg" },
  heart_rate: { label: "Heart rate", short: "HR", unit: "/min" },
  respiratory_rate: { label: "Respiratory rate", short: "RR", unit: "/min" },
  temperature: { label: "Temperature", short: "T", unit: "°C" },
  spo2: { label: "SpO₂", short: "SpO₂", unit: "%" },
  weight: { label: "Weight", short: "Wt", unit: "kg" },
  blood_glucose: { label: "Blood glucose", short: "BG", unit: "mg/dL" },
};

/** UCUM unit stored by the API for each kind. */
export const UCUM: Record<VitalKind, string> = {
  systolic_bp: "mm[Hg]",
  diastolic_bp: "mm[Hg]",
  heart_rate: "/min",
  respiratory_rate: "/min",
  temperature: "Cel",
  spo2: "%",
  weight: "kg",
  blood_glucose: "mg/dL",
};

export function isVitalKind(kind: string): kind is VitalKind {
  return (VITAL_KINDS as string[]).includes(kind);
}

export const FLAG_META: Record<Flag, { label: string; icon: string; className: string }> = {
  normal: {
    label: "Normal",
    icon: "✓",
    className: "bg-ok-soft text-ok-fg ring-ok-line",
  },
  warning: {
    label: "Warning",
    icon: "▲",
    className: "bg-warn-soft text-warn-fg ring-warn-line",
  },
  critical: {
    label: "Critical",
    icon: "⬣",
    className: "bg-bad-soft text-bad-fg ring-bad-line",
  },
};

const ORDER: Record<Flag, number> = { normal: 0, warning: 1, critical: 2 };

export function worstFlag(flags: Flag[]): Flag {
  return flags.reduce<Flag>((worst, f) => (ORDER[f] > ORDER[worst] ? f : worst), "normal");
}

export function isFlag(value: string): value is Flag {
  return value === "normal" || value === "warning" || value === "critical";
}
