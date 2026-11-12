import type { ReactNode } from "react";

import { AlertIcon } from "@/shared/ui/icons";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="text-ink-3 flex items-center justify-center gap-3 py-12 text-sm">
      <span
        aria-hidden="true"
        className="border-line-strong border-t-brand inline-block size-4 animate-spin rounded-full border-2 motion-reduce:animate-none"
      />
      {label}
    </p>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-900/60 dark:bg-red-950/50 dark:text-red-100"
    >
      <AlertIcon className="mt-0.5 shrink-0" size={16} />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="card flex flex-col items-center px-6 py-14 text-center">
      {icon && (
        <span className="bg-surface-3 text-ink-3 mb-4 flex size-12 items-center justify-center rounded-2xl">
          {icon}
        </span>
      )}
      <p className="text-ink font-semibold">{title}</p>
      {children && <div className="text-ink-3 mt-1 max-w-sm text-sm">{children}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  eyebrow,
  subtitle,
  actions,
}: {
  title: string;
  eyebrow?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="text-ink text-[2rem] leading-tight font-semibold tracking-[-0.03em]">
          {title}
        </h1>
        {subtitle && <p className="text-ink-2 mt-2 max-w-2xl text-[15px]">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Pill for neutral metadata (status, counts). Tones carry text too, never colour alone. */
export function Pill({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: "neutral" | "brand" | "info" | "danger" | "success";
  children: ReactNode;
  className?: string;
}) {
  const tones = {
    neutral: "bg-surface-3 text-ink-2 ring-line-strong/60",
    brand: "bg-brand-soft text-brand-text ring-brand/20",
    info: "bg-sky-50 text-sky-900 ring-sky-600/20 dark:bg-sky-950/60 dark:text-sky-100 dark:ring-sky-400/20",
    danger:
      "bg-red-50 text-red-900 ring-red-600/20 dark:bg-red-950/60 dark:text-red-100 dark:ring-red-400/20",
    success:
      "bg-emerald-50 text-emerald-900 ring-emerald-600/20 dark:bg-emerald-950/60 dark:text-emerald-100 dark:ring-emerald-400/20",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
