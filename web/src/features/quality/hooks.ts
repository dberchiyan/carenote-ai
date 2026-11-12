"use client";

import { useQuery } from "@tanstack/react-query";

import { qualityApi } from "./api";
import { qualityKeys } from "./keys";

export function useEvalRuns() {
  return useQuery({
    queryKey: qualityKeys.evals(),
    queryFn: qualityApi.evals,
    staleTime: Infinity,
  });
}

export function useCorrections(days: number) {
  return useQuery({
    queryKey: qualityKeys.corrections(days),
    queryFn: () => qualityApi.corrections(days),
  });
}
