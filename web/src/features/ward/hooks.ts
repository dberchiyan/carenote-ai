"use client";

import { useQuery } from "@tanstack/react-query";

import { wardApi } from "./api";
import { wardKeys } from "./keys";

/** The ward's patients with their latest confirmed vitals (the caller's ward by default). */
export function usePatients(ward?: string) {
  return useQuery({ queryKey: wardKeys.patients(ward), queryFn: () => wardApi.patients(ward) });
}
