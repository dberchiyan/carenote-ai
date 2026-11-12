"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { AlertIcon, CheckIcon, XIcon } from "@/shared/ui/icons";

export type Toast = {
  id: number;
  title: string;
  description?: string;
  tone: "success" | "info" | "danger";
};
type ToastInput = Omit<Toast, "id" | "tone"> & { tone?: Toast["tone"] };

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);
export const TOAST_MS = 4500;

export function useToast(): (toast: ToastInput) => void {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast needs a ToastProvider");
  return push;
}

/** Bottom-right stack of short confirmations. Announced politely; dismissable; auto-hides. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const dismiss = useCallback((id: number) => {
    setToasts((all) => all.filter((t) => t.id !== id));
  }, []);
  const push = useCallback(
    (toast: ToastInput) => {
      const id = nextId.current++;
      setToasts((all) => [...all.slice(-2), { tone: "success", ...toast, id }]);
      setTimeout(() => dismiss(id), TOAST_MS);
    },
    [dismiss],
  );
  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-50 flex flex-col items-end gap-2 sm:inset-x-auto sm:right-6 lg:bottom-6"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className="card shadow-lift animate-rise pointer-events-auto flex w-full max-w-sm items-start gap-3 px-4 py-3"
          >
            <span
              className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full ${
                t.tone === "danger"
                  ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
                  : t.tone === "info"
                    ? "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300"
                    : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
              }`}
            >
              {t.tone === "danger" ? <AlertIcon size={14} /> : <CheckIcon size={14} />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="text-ink block text-sm font-semibold">{t.title}</span>
              {t.description && (
                <span className="text-ink-3 mt-0.5 block text-xs leading-relaxed">
                  {t.description}
                </span>
              )}
            </span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="text-ink-3 hover:bg-surface-3 hover:text-ink focus-visible:outline-brand-ring -mr-1 flex size-7 shrink-0 items-center justify-center rounded-md focus-visible:outline-2"
            >
              <XIcon size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
