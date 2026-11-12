export const patientKeys = {
  all: ["patients"] as const,
  detail: (id: string) => ["patients", "detail", id] as const,
  observations: (id: string, days?: number) =>
    days === undefined
      ? (["patients", "observations", id] as const)
      : (["patients", "observations", id, days] as const),
  rules: () => ["alert-rules"] as const,
};
