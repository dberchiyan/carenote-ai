import { z } from "zod";

/**
 * Server-side environment, validated once at first use. A misconfigured deployment fails on the
 * first proxied request with a clear message instead of forwarding to the wrong host.
 */
const schema = z.object({
  API_INTERNAL_URL: z.url().default("http://localhost:8000"),
});

let cached: z.infer<typeof schema> | undefined;

export function serverEnv(): z.infer<typeof schema> {
  cached ??= schema.parse({ API_INTERNAL_URL: process.env.API_INTERNAL_URL || undefined });
  return cached;
}
