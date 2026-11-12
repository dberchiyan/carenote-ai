import { api } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";

export const handoverApi = {
  shift: async (hours: number) =>
    unwrap(await api.GET("/handover", { params: { query: { hours } } })),
};
