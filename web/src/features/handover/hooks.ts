"use client";

import { useQuery } from "@tanstack/react-query";

import { handoverApi } from "./api";
import { handoverKeys } from "./keys";

export function useHandover(hours: number) {
  return useQuery({
    queryKey: handoverKeys.shift(hours),
    queryFn: () => handoverApi.shift(hours),
    placeholderData: (previous) => previous,
  });
}
