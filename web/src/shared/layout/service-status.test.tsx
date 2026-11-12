import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ServiceStatus, StatusBadge } from "@/shared/layout/service-status";

function stubApi(response: Response) {
  const fetchMock = vi.fn(async (input: Request) => {
    expect(new URL(input.url).pathname).toBe("/api/health/ready");
    return response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("StatusBadge", () => {
  it("uses text, not only colour, to convey status", () => {
    render(<StatusBadge status="unavailable" />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });
});

describe("ServiceStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows operational when the API is ready", async () => {
    const fetchMock = stubApi(Response.json({ status: "ok", database: "ok" }));
    renderWithQuery(<ServiceStatus />);
    expect(await screen.findByText("Operational")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("shows unavailable when the database is down", async () => {
    const fetchMock = stubApi(
      Response.json({ status: "unavailable", database: "unavailable" }, { status: 503 }),
    );
    renderWithQuery(<ServiceStatus />);
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
