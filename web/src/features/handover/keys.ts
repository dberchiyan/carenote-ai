export const handoverKeys = {
  all: ["handover"] as const,
  shift: (hours: number) => ["handover", hours] as const,
};
