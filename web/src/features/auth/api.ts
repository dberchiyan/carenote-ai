import { api } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";
import type { Role, User } from "@/shared/api/types";

export const ROLE_LABELS: Record<Role, string> = {
  nurse: "Nurse",
  charge_nurse: "Charge nurse",
  auditor: "Auditor",
};

/** Where each role lands after login. */
export function homeFor(user: User): string {
  return user.role === "auditor" ? "/audit" : "/ward";
}

export const authApi = {
  me: async () => unwrap(await api.GET("/auth/me")),
  demoUsers: async () => unwrap(await api.GET("/auth/demo-users")),
  login: async (username: string) =>
    unwrap(await api.POST("/auth/demo-login", { body: { username } })),
  logout: async () => unwrap(await api.POST("/auth/logout")),
};
