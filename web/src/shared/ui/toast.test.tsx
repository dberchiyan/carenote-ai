import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TOAST_MS, ToastProvider, useToast } from "@/shared/ui/toast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast({ title: "Note confirmed", description: "Saved." })}>
      go
    </button>
  );
}

describe("toast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows a confirmation, lets the user dismiss it, and hides it by itself", () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    act(() => screen.getByText("go").click());
    expect(screen.getByRole("status")).toHaveTextContent("Note confirmed");
    expect(screen.getByRole("status")).toHaveTextContent("Saved.");

    act(() => screen.getByText("go").click());
    expect(screen.getAllByRole("status")).toHaveLength(2);
    act(() => screen.getAllByLabelText("Dismiss")[0]?.click());
    expect(screen.getAllByRole("status")).toHaveLength(1);

    act(() => vi.advanceTimersByTime(TOAST_MS + 1));
    expect(screen.queryByRole("status")).toBeNull();
  });
});
