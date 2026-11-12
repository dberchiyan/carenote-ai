import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Absolute URL: `Request` rejects relative URLs outside a real browser (jsdom, server).
const origin = typeof window === "undefined" ? "http://localhost:3000" : window.location.origin;

// Typed API client. Types are generated from the FastAPI OpenAPI schema (`make types`).
export const api = createClient<paths>({
  baseUrl: `${origin}/api`,
  // Resolve `fetch` per call so tests can stub it.
  fetch: (request) => globalThis.fetch(request),
});
