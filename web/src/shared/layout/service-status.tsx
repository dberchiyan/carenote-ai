"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";

type Status = "checking" | "ok" | "unavailable";

export function useApiStatus(): Status {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health", "ready"],
    queryFn: async (): Promise<Status> => {
      // A 503 is a valid answer here ("not ready"), not an error to throw.
      const { data, response } = await api.GET("/health/ready");
      return response.ok && data?.status === "ok" ? "ok" : "unavailable";
    },
    refetchInterval: 15_000,
  });
  if (isPending) return "checking";
  return isError ? "unavailable" : data;
}

const LABELS: Record<Status, string> = {
  checking: "Checking…",
  ok: "Operational",
  unavailable: "Unavailable",
};

export function StatusBadge({ status }: { status: Status }) {
  const tone =
    status === "ok"
      ? "bg-emerald-50 text-emerald-900 ring-emerald-600/25 dark:bg-emerald-950/60 dark:text-emerald-100 dark:ring-emerald-400/25"
      : status === "unavailable"
        ? "bg-red-50 text-red-900 ring-red-600/25 dark:bg-red-950/60 dark:text-red-100 dark:ring-red-400/25"
        : "bg-surface-3 text-ink-2 ring-line-strong";
  const icon = status === "ok" ? "●" : status === "unavailable" ? "▲" : "○";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${tone}`}
    >
      <span aria-hidden="true">{icon}</span>
      {LABELS[status]}
    </span>
  );
}

export function ServiceStatus() {
  const status = useApiStatus();
  return (
    <p className="flex items-center gap-3" aria-live="polite">
      <span>API</span>
      <StatusBadge status={status} />
    </p>
  );
}
