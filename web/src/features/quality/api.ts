import { api } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";

export const qualityApi = {
  evals: async () => unwrap(await api.GET("/quality/evals")),
  corrections: async (days: number) =>
    unwrap(await api.GET("/quality/corrections", { params: { query: { days } } })),
};
