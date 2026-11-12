// Liveness of the web container (used by the Docker healthcheck).
export function GET(): Response {
  return Response.json({ status: "ok" });
}
