import { api } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";

export const wardApi = {
  patients: async (ward?: string) =>
    unwrap(await api.GET("/patients", { params: { query: { ward } } })),
};
