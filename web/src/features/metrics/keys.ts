export const metricsKeys = {
  llm: (days: number) => ["metrics", "llm", days] as const,
};
