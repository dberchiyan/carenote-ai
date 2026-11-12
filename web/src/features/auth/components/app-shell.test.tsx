import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { authKeys } from "@/features/auth/keys";
import type { User } from "@/shared/api/types";

import { AppShell } from "./app-shell";

const navigation = vi.hoisted(() => ({ pathname: "/ward", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ replace: navigation.replace, push: vi.fn() }),
}));

function renderShell(user: User, pathname: string) {
  navigation.pathname = pathname;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(authKeys.me(), user);
  render(
    <QueryClientProvider client={client}>
      <AppShell>
        <p>page content</p>
      </AppShell>
    </QueryClientProvider>,
  );
}

const nurse = {
  id: "u1",
  username: "nurse",
  display_name: "Nora",
  role: "nurse",
  ward: "3A",
} as User;
const auditor = {
  id: "u2",
  username: "auditor",
  display_name: "Aisha",
  role: "auditor",
  ward: null,
} as User;

describe("AppShell", () => {
  it("shows each role its own navigation", () => {
    renderShell(nurse, "/ward");
    expect(screen.getByRole("link", { name: "Ward" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Audit log" })).not.toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("refuses a page outside the role up front instead of rendering it", () => {
    renderShell(auditor, "/notes/new");
    expect(screen.getByRole("heading", { name: "No access to this page" })).toBeInTheDocument();
    expect(screen.queryByText("page content")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to your home page" })).toHaveAttribute(
      "href",
      "/audit",
    );
  });
});
