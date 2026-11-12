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
    className:
      "bg-emerald-50 text-emerald-900 ring-emerald-600/25 dark:bg-emerald-950/60 dark:text-emerald-100 dark:ring-emerald-400/25",
  },
  warning: {
    label: "Warning",
    icon: "▲",
    className:
      "bg-amber-50 text-amber-950 ring-amber-600/35 dark:bg-amber-950/60 dark:text-amber-100 dark:ring-amber-400/30",
  },
  critical: {
    label: "Critical",
    icon: "⬣",
    className:
      "bg-red-50 text-red-900 ring-red-600/30 dark:bg-red-950/60 dark:text-red-100 dark:ring-red-400/30",
  },
};

const ORDER: Record<Flag, number> = { normal: 0, warning: 1, critical: 2 };

export function worstFlag(flags: Flag[]): Flag {
  return flags.reduce<Flag>((worst, f) => (ORDER[f] > ORDER[worst] ? f : worst), "normal");
}

export function isFlag(value: string): value is Flag {
  return value === "normal" || value === "warning" || value === "critical";
}
