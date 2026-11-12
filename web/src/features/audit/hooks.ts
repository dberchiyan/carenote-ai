"use client";

import { useQuery } from "@tanstack/react-query";

import { auditApi, type AuditFilters } from "./api";
import { auditKeys } from "./keys";

export type { AuditFilters } from "./api";

export function useAuditEvents(filters: AuditFilters, offset: number) {
  return useQuery({
    queryKey: auditKeys.list(filters, offset),
    queryFn: () => auditApi.list(filters, offset),
    // Keep the previous page on screen while the next one loads.
    placeholderData: (previous) => previous,
  });
}

/** Action names that exist in the log, for the filter: never a list that drifts from the API. */
export function useAuditActions() {
  return useQuery({ queryKey: auditKeys.actions(), queryFn: auditApi.actions, staleTime: 60_000 });
}
