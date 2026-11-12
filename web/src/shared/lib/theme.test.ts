import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { applyTheme, readTheme, THEME_KEY, useTheme } from "@/shared/lib/theme";

describe("theme", () => {
  beforeEach(() => {
    // jsdom's storage is partial; a Map-backed stand-in is enough for the three calls we make.
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    });
    delete document.documentElement.dataset.theme;
  });

  it("marks the root for an explicit theme and clears it for system", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("ignores junk in storage", () => {
    localStorage.setItem(THEME_KEY, "neon");
    expect(readTheme()).toBe("system");
  });

  it("persists the choice and applies it", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("light"));
    expect(result.current[0]).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    act(() => result.current[1]("system"));
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });
});
