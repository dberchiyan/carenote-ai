"use client";

import { useQuery } from "@tanstack/react-query";

import { patientsApi } from "./api";
import { patientKeys } from "./keys";

export { patientsApi } from "./api";

export function usePatient(id: string) {
  return useQuery({ queryKey: patientKeys.detail(id), queryFn: () => patientsApi.get(id) });
}

export function useObservations(id: string, days: number) {
  return useQuery({
    queryKey: patientKeys.observations(id, days),
    queryFn: () => patientsApi.observations(id, days),
  });
}

export function useRules() {
  return useQuery({
    queryKey: patientKeys.rules(),
    queryFn: patientsApi.rules,
    staleTime: Infinity,
  });
}
