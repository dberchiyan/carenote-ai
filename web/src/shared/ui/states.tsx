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
      className="border-bad-line bg-bad-soft text-bad-fg flex items-start gap-3 rounded-xl border px-4 py-3 text-sm"
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
      {children && <div className="text-ink-3 mt-1 w-full max-w-sm text-sm">{children}</div>}
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
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 sm:mb-8">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-1.5 sm:mb-2">{eyebrow}</p>}
        <h1 className="text-ink text-[1.625rem] leading-tight font-semibold tracking-[-0.03em] sm:text-[2rem]">
          {title}
        </h1>
        {subtitle && (
          <p className="text-ink-2 mt-1.5 max-w-2xl text-sm sm:mt-2 sm:text-[15px]">{subtitle}</p>
        )}
      </div>
      {actions && (
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto [&>*]:flex-1 sm:[&>*]:flex-none">
          {actions}
        </div>
      )}
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
    info: "bg-info-soft text-info-fg ring-info-line",
    danger: "bg-bad-soft text-bad-fg ring-bad-line",
    success: "bg-ok-soft text-ok-fg ring-ok-line",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
