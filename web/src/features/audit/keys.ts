import type { AuditFilters } from "./api";

export const auditKeys = {
  all: ["audit"] as const,
  actions: () => ["audit", "actions"] as const,
  list: (filters: AuditFilters, offset: number) => ["audit", "list", filters, offset] as const,
};
