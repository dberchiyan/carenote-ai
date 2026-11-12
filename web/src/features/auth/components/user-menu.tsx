"use client";

import { useEffect, useId, useRef, useState } from "react";

import type { User } from "@/shared/api/types";
import { ROLE_LABELS } from "@/features/auth/hooks";
import { initials } from "@/shared/lib/format";

import { ThemeToggle } from "@/shared/layout/theme-toggle";
import { ChevronDownIcon, LogoutIcon } from "@/shared/ui/icons";

/**
 * Account menu in the top bar: who is signed in, the theme, sign out.
 * Opens on click, closes on Escape, outside click or focus leaving it; the trigger gets focus back.
 */
export function UserMenu({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const subtitle = `${ROLE_LABELS[user.role]}${user.ward ? ` · Ward ${user.ward}` : ""}`;

  return (
    <div
      ref={root}
      className="relative"
      onBlur={(e) => {
        if (!root.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={`Account: ${user.display_name}, ${subtitle}`}
        className="hover:bg-surface-3 focus-visible:outline-brand-ring flex items-center gap-2 rounded-full py-1 pr-2 pl-1 transition-colors focus-visible:outline-2"
      >
        <span
          aria-hidden="true"
          className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-teal-300 to-teal-600 text-xs font-semibold text-teal-950"
        >
          {initials(user.display_name)}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="text-ink block text-sm font-medium">{user.display_name}</span>
          <span className="text-ink-3 block text-[11px]">{subtitle}</span>
        </span>
        <ChevronDownIcon
          size={14}
          className={`text-ink-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          id={menuId}
          role="dialog"
          aria-label="Account"
          className="card shadow-lift animate-rise absolute right-0 z-40 mt-2 w-72 p-2"
        >
          <div className="flex items-center gap-3 px-2 py-2">
            <span
              aria-hidden="true"
              className="flex size-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal-300 to-teal-600 text-sm font-semibold text-teal-950"
            >
              {initials(user.display_name)}
            </span>
            <span className="min-w-0 leading-tight">
              <span className="text-ink block truncate text-sm font-semibold">
                {user.display_name}
              </span>
              <span className="text-ink-3 block truncate text-xs">{subtitle}</span>
            </span>
          </div>
          <div className="border-line my-2 border-t" />
          <div className="px-2 py-1.5">
            <p className="text-ink-3 mb-1.5 text-[11px] font-semibold tracking-[0.06em] uppercase">
              Theme
            </p>
            <ThemeToggle />
          </div>
          <div className="border-line my-2 border-t" />
          <button
            type="button"
            onClick={onSignOut}
            className="text-ink hover:bg-surface-3 focus-visible:outline-brand-ring flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-sm font-medium focus-visible:outline-2"
          >
            <LogoutIcon size={16} className="text-ink-3" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
