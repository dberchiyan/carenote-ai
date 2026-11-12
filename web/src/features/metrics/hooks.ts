"use client";

import { useQuery } from "@tanstack/react-query";

import { metricsApi } from "./api";
import { metricsKeys } from "./keys";

export function useLlmMetrics(days: number) {
  return useQuery({ queryKey: metricsKeys.llm(days), queryFn: () => metricsApi.llm(days) });
}
