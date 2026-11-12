import { api } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";

export const metricsApi = {
  llm: async (days: number) =>
    unwrap(await api.GET("/metrics/llm", { params: { query: { days } } })),
};
