"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { isApiError } from "@/shared/api/errors";

import { authApi } from "./api";
import { authKeys } from "./keys";

export { homeFor, ROLE_LABELS } from "./api";

export function useMe() {
  return useQuery({
    queryKey: authKeys.me(),
    queryFn: authApi.me,
    retry: (count, error) => !isApiError(error, "unauthenticated") && count < 2,
  });
}

export function useDemoUsers() {
  return useQuery({ queryKey: authKeys.demoUsers(), queryFn: authApi.demoUsers });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (user) => {
      queryClient.clear();
      queryClient.setQueryData(authKeys.me(), user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: authApi.logout, onSettled: () => queryClient.clear() });
}
