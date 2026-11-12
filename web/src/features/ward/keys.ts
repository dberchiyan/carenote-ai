export const wardKeys = {
  all: ["ward"] as const,
  patients: (ward: string | undefined) => ["ward", "patients", ward ?? "own"] as const,
};
