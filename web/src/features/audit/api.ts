import { api } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";

export type AuditFilters = { entity?: string; entity_id?: string; action?: string };

export const auditApi = {
  actions: async () => unwrap(await api.GET("/audit/actions")),
  list: async (filters: AuditFilters, offset: number) =>
    unwrap(
      await api.GET("/audit", {
        params: {
          query: {
            entity: filters.entity || undefined,
            entity_id: filters.entity_id || undefined,
            action: filters.action || undefined,
            offset,
          },
        },
      }),
    ),
};
