import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { User } from "@/shared/api/types";

import { markGuideStep } from "../hooks";
import { GuideMenu } from "./guide-menu";

const nav = vi.hoisted(() => ({ pathname: "/ward" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

const nurse = {
  id: "u-nurse",
  username: "nurse",
  display_name: "Nora Lindqvist",
  role: "nurse",
  ward: "3A",
} as User;

// Node's own (file-less) localStorage shadows jsdom's here: give the guide a plain in-memory one.
function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (k) => data.get(k) ?? null,
    key: (i) => [...data.keys()][i] ?? null,
    removeItem: (k) => void data.delete(k),
    setItem: (k, v) => void data.set(k, String(v)),
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", memoryStorage());
  nav.pathname = "/ward";
});

describe("GuideMenu", () => {
  it("opens by itself on a viewer's first visit only", () => {
    const first = render(<GuideMenu user={nurse} onSwitchRole={() => {}} />);
    expect(screen.getByRole("dialog", { name: "Demo guide" })).toHaveTextContent("Welcome, Nora");
    first.unmount();
    render(<GuideMenu user={nurse} onSwitchRole={() => {}} />);
    expect(screen.queryByRole("dialog", { name: "Demo guide" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Demo guide, 0 of 4 steps done" }),
    ).toBeInTheDocument();
  });

  it("ticks a page step on arrival and an action step when the app reports it", async () => {
    nav.pathname = "/notes/00000000-0000-4000-8000-000000000001";
    render(<GuideMenu user={nurse} onSwitchRole={() => {}} />);
    expect(screen.getByRole("button", { name: /1 of 4 steps done/ })).toBeInTheDocument();
    act(() => markGuideStep("note-confirmed"));
    const panel = screen.getByRole("dialog", { name: "Demo guide" });
    expect(within(panel).getByText(/Check and confirm the draft/)).toHaveTextContent("(done)");
    expect(screen.getByRole("button", { name: /2 of 4 steps done/ })).toBeInTheDocument();
  });

  it("points to the next role when the loop is done, and can restart", async () => {
    const onSwitchRole = vi.fn();
    localStorage.setItem(
      "carenote.guide.v1.u-nurse",
      JSON.stringify({ seen: true, done: ["record", "confirm", "record-view", "fhir"] }),
    );
    render(<GuideMenu user={nurse} onSwitchRole={onSwitchRole} />);
    await userEvent.click(screen.getByRole("button", { name: /4 of 4 steps done/ }));
    expect(screen.getByText(/Sign in as Carlos Mendes/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Switch role" }));
    expect(onSwitchRole).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Restart the guide" }));
    expect(screen.getByRole("button", { name: /0 of 4 steps done/ })).toBeInTheDocument();
  });
});
