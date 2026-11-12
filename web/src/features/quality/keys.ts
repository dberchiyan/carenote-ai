export const qualityKeys = {
  evals: () => ["quality", "evals"] as const,
  corrections: (days: number) => ["quality", "corrections", days] as const,
};
