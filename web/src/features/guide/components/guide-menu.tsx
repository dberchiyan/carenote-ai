"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import type { User } from "@/shared/api/types";
import { CheckIcon, ChevronRightIcon, SparkIcon, UndoIcon, XIcon } from "@/shared/ui/icons";

import { onGuideEvent, useGuideProgress } from "../hooks";
import { GUIDES } from "../steps";

/** A small ring that fills as steps are done; the count is beside it. */
function ProgressRing({
  value,
  total,
  size = 18,
}: {
  value: number;
  total: number;
  size?: number;
}) {
  const r = (size - 3) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden="true"
      className="-rotate-90"
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--line-strong)"
        strokeWidth={2.5}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--brand)"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - value / total)}
        className="transition-[stroke-dashoffset] duration-500 motion-reduce:transition-none"
      />
    </svg>
  );
}

/**
 * The demo guide: a role-specific checklist in the top bar. Opens by itself on a viewer's first
 * visit, ticks steps as they happen (a page visited, a note confirmed, a bundle exported), and
 * points to the next role when the loop is done. Progress stays in this browser.
 */
export function GuideMenu({ user, onSwitchRole }: { user: User; onSwitchRole: () => void }) {
  const guide = GUIDES[user.role];
  const pathname = usePathname();
  const { done, complete, firstVisit, reset } = useGuideProgress(user.id);
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  const count = guide.steps.filter((s) => done.has(s.id)).length;
  const total = guide.steps.length;
  const finished = count === total;

  // First visit for this viewer: introduce the guide once.
  useEffect(() => {
    // Automated browsers (end-to-end tests) start closed so the panel never covers what they click.
    if (firstVisit() && !navigator.webdriver) setOpen(true);
  }, [firstVisit]);

  // Steps that are "go to this page".
  useEffect(() => {
    for (const step of guide.steps) if (step.route?.test(pathname)) complete(step.id);
  }, [pathname, guide.steps, complete]);

  // Steps that are "do this": the app reports them.
  useEffect(
    () =>
      onGuideEvent((event) => {
        for (const step of guide.steps) if (step.event === event) complete(step.id);
      }),
    [guide.steps, complete],
  );

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

  const nextStep = guide.steps.find((s) => !done.has(s.id));
  const firstName = user.display_name.split(" ")[0] ?? user.display_name;

  return (
    <div ref={root} className="relative">
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Demo guide, ${count} of ${total} steps done`}
        className={`focus-visible:outline-brand-ring flex h-9 items-center gap-2 rounded-full px-2.5 text-sm font-medium transition-colors focus-visible:outline-2 ${
          finished
            ? "text-ink-3 hover:bg-surface-3"
            : "bg-brand-soft text-brand-text ring-brand/20 hover:bg-brand-soft/70 ring-1 ring-inset"
        }`}
      >
        {finished ? <CheckIcon size={16} /> : <ProgressRing value={count} total={total} />}
        <span className="hidden sm:inline">Guide</span>
        <span className="tabular-nums">
          {count}/{total}
        </span>
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label="Demo guide"
          className="card shadow-lift animate-rise fixed inset-x-3 top-14 z-40 max-h-[calc(100dvh-9.5rem-env(safe-area-inset-bottom))] overflow-y-auto overscroll-contain sm:absolute sm:inset-x-auto sm:top-auto sm:right-0 sm:mt-2 sm:max-h-[calc(100dvh-5rem)] sm:w-[23rem]"
        >
          <div className="from-brand-soft to-surface relative bg-gradient-to-b px-5 pt-5 pb-4">
            <button
              type="button"
              aria-label="Close guide"
              onClick={() => setOpen(false)}
              className="text-ink-3 hover:bg-surface-3 hover:text-ink focus-visible:outline-brand-ring absolute top-3 right-3 flex size-8 items-center justify-center rounded-full focus-visible:outline-2"
            >
              <XIcon size={16} />
            </button>
            <span className="bg-surface text-brand-text ring-brand/20 mb-3 inline-flex size-9 items-center justify-center rounded-xl ring-1">
              <SparkIcon size={17} />
            </span>
            <p className="text-ink text-base font-semibold tracking-[-0.01em]">
              {finished ? `Nice work, ${firstName}` : `Welcome, ${firstName}`}
            </p>
            <p className="text-ink-2 mt-1 text-sm leading-relaxed">{guide.intro}</p>
            <div className="mt-4 flex items-center gap-3">
              <span
                className="bg-line h-1.5 flex-1 overflow-hidden rounded-full"
                role="progressbar"
                aria-label="Guide progress"
                aria-valuemin={0}
                aria-valuemax={total}
                aria-valuenow={count}
              >
                <span
                  className="bg-brand block h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none"
                  style={{ width: `${(count / total) * 100}%` }}
                />
              </span>
              <span className="text-ink-3 text-xs tabular-nums">
                {count} of {total}
              </span>
            </div>
          </div>

          <ol className="flex flex-col gap-1 p-2">
            {guide.steps.map((step, i) => {
              const isDone = done.has(step.id);
              const isNext = step === nextStep;
              return (
                <li key={step.id}>
                  <div
                    className={`flex items-start gap-3 rounded-xl px-3 py-2.5 ${
                      isNext ? "bg-surface-2 ring-line ring-1 ring-inset" : ""
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                        isDone
                          ? "bg-brand text-brand-fg"
                          : isNext
                            ? "ring-brand text-brand-text ring-2 ring-inset"
                            : "ring-line-strong text-ink-3 ring-1 ring-inset"
                      }`}
                    >
                      {isDone ? <CheckIcon size={13} /> : i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span
                        className={`block text-sm font-medium ${isDone ? "text-ink-3 line-through decoration-1" : "text-ink"}`}
                      >
                        {step.title}
                        <span className="sr-only">{isDone ? " (done)" : ""}</span>
                      </span>
                      {!isDone && (
                        <span className="text-ink-3 mt-0.5 block text-xs leading-relaxed">
                          {step.description}
                        </span>
                      )}
                    </span>
                    {!isDone && (
                      <Link
                        href={step.href}
                        onClick={() => setOpen(false)}
                        className={`focus-visible:outline-brand-ring mt-0.5 inline-flex shrink-0 items-center gap-0.5 rounded-lg px-2 py-1 text-xs font-semibold focus-visible:outline-2 ${
                          isNext
                            ? "bg-brand text-brand-fg hover:bg-brand-strong"
                            : "text-brand-text hover:bg-brand-soft"
                        }`}
                      >
                        Go
                        <ChevronRightIcon size={13} />
                      </Link>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>

          <div className="border-line flex items-center justify-between gap-3 border-t px-4 py-3">
            {finished && guide.next ? (
              <p className="text-ink-2 text-xs leading-relaxed">{guide.next}</p>
            ) : (
              <p className="text-ink-3 text-xs">Synthetic data only. Steps tick as you go.</p>
            )}
            <div className="flex shrink-0 items-center gap-1">
              {count > 0 && (
                <button
                  type="button"
                  onClick={reset}
                  aria-label="Restart the guide"
                  title="Restart"
                  className="text-ink-3 hover:bg-surface-3 hover:text-ink focus-visible:outline-brand-ring flex size-8 items-center justify-center rounded-lg focus-visible:outline-2"
                >
                  <UndoIcon size={15} />
                </button>
              )}
              {finished && guide.next && (
                <button
                  type="button"
                  onClick={onSwitchRole}
                  className="bg-brand text-brand-fg hover:bg-brand-strong focus-visible:outline-brand-ring rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap focus-visible:outline-2"
                >
                  Switch role
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
