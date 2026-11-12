import { mkdir } from "node:fs/promises";
import path from "node:path";

import { request, type FullConfig } from "@playwright/test";

export const ROLES = ["nurse", "charge", "auditor", "nurse_b"] as const;
export const STATE_DIR = path.join(__dirname, "..", "..", "test-results", "state");

export function stateFile(role: (typeof ROLES)[number]): string {
  return path.join(STATE_DIR, `${role}.json`);
}

/** Sign each demo user in once and keep the cookie: specs reuse it instead of logging in. */
export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use.baseURL ?? "http://localhost:3000";
  await mkdir(STATE_DIR, { recursive: true });
  for (const role of ROLES) {
    const api = await request.newContext({ baseURL });
    const response = await api.post("/api/auth/demo-login", { data: { username: role } });
    if (!response.ok()) throw new Error(`demo login as ${role}: ${response.status()}`);
    await api.storageState({ path: stateFile(role) });
    await api.dispose();
  }
}
