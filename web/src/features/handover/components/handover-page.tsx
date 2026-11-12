"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";

import { useHandover } from "@/features/handover/hooks";
import { isFlag } from "@/shared/lib/vitals";
import { formatDateTime } from "@/shared/lib/format";
import { usePageTitle } from "@/shared/lib/use-page-title";
import { useUrlState } from "@/shared/lib/use-url-state";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Select } from "@/shared/ui/field";
import { FlagBadge } from "@/shared/ui/flag-badge";
import {
  AlertIcon,
  CheckIcon,
  ChevronRightIcon,
  ClipboardIcon,
  CopyIcon,
  FileIcon,
  PillIcon,
  PrinterIcon,
  SparkIcon,
  UploadIcon,
} from "@/shared/ui/icons";
import { CardSkeleton, SkeletonStatus } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState, PageHeader, Pill } from "@/shared/ui/states";
import { useToast } from "@/shared/ui/toast";

import {
  formatVital,
  handoverText,
  mergeBloodPressure,
  needsAttention,
  trend,
  type Handover,
  type HandoverPatient,
  type VitalChip,
} from "../lib/text";

const WINDOWS = [8, 12, 24];

type Priority = HandoverPatient["priority"];

const PRIORITY: Record<
  Priority,
  { label: string; dot: string; tone: "danger" | "info" | "neutral" | "success" }
> = {
  critical: { label: "Critical", dot: "bg-bad", tone: "danger" },
  warning: { label: "Warning", dot: "bg-warn", tone: "neutral" },
  review: { label: "Awaiting review", dot: "bg-info", tone: "info" },
  stable: { label: "Stable", dot: "bg-ok", tone: "success" },
};

const SECTIONS: {
  id: string;
  title: string;
  short: string;
  hint: string;
  match: Priority[];
}[] = [
  {
    id: "needs-attention",
    title: "Needs attention",
    short: "Attention",
    hint: "Critical or warning values this shift",
    match: ["critical", "warning"],
  },
  {
    id: "awaiting-review",
    title: "Awaiting review",
    short: "Review",
    hint: "Drafts not yet confirmed",
    match: ["review"],
  },
  {
    id: "stable",
    title: "Stable",
    short: "Stable",
    hint: "No flagged values this shift",
    match: ["stable"],
  },
];

const TILE: Record<VitalChip["flag"], string> = {
  critical: "bg-bad-soft ring-bad-line print:bg-transparent",
  warning: "bg-warn-soft ring-warn-line print:bg-transparent",
  normal: "bg-surface-2 ring-line",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function PriorityIcon({ priority, size = 12 }: { priority: Priority; size?: number }) {
  if (priority === "critical" || priority === "warning") return <AlertIcon size={size} />;
  if (priority === "stable") return <CheckIcon size={size} />;
  return <FileIcon size={size} />;
}

function Trend({ v, className = "" }: { v: VitalChip; className?: string }) {
  const t = trend(v);
  if (!t) return null;
  return (
    <span className={`inline-flex items-center gap-1 tabular-nums ${className}`}>
      <span aria-hidden="true">{t === "up" ? "↑" : "↓"}</span>
      <span>
        <span className="sr-only">{t === "up" ? "up" : "down"} from </span>
        <span aria-hidden="true">was </span>
        {v.previous}
      </span>
    </span>
  );
}

function ChangeTag({ v }: { v: VitalChip }) {
  if (v.change !== "new_flag" && v.change !== "worse") return null;
  return (
    <span className="bg-bad-soft text-bad-fg ring-bad-line rounded-md px-1.5 py-px text-[10px] font-bold tracking-wider uppercase ring-1 ring-inset">
      {v.change === "new_flag" ? "new" : "worse"}
    </span>
  );
}

/** A flagged value as a tile: the number large, the context underneath. */
function VitalTile({ v }: { v: VitalChip }) {
  const backToNormal = v.flag === "normal" && v.worst_in_shift !== "normal";
  return (
    <li className={`rounded-xl p-3 ring-1 ring-inset ${TILE[v.flag]}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-ink-2 text-[11px] font-semibold tracking-wide uppercase">
          {v.label}
        </span>
        {v.flag !== "normal" && isFlag(v.flag) && <FlagBadge flag={v.flag} compact />}
      </div>
      <p className="text-ink mt-1 text-[1.375rem] leading-none font-semibold tracking-[-0.02em] tabular-nums">
        {v.display ?? v.value}
        <span className="text-ink-3 ml-1 text-xs font-medium tracking-normal">{v.unit}</span>
      </p>
      <p className="text-ink-3 mt-2 flex min-h-4 flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <Trend v={v} />
        <ChangeTag v={v} />
        {backToNormal && <span>back to normal, was {v.worst_in_shift} this shift</span>}
      </p>
    </li>
  );
}

/** The quiet values, one line: "RR 13 /min ↑ · HR 61 /min · Temp 37°C". */
function QuietVitals({ vitals, lead }: { vitals: VitalChip[]; lead?: string }) {
  if (vitals.length === 0) return null;
  return (
    <p className="text-ink-2 flex flex-wrap items-baseline gap-x-1 text-sm">
      {lead && <span className="text-ink-3 mr-1 text-xs font-medium">{lead}</span>}
      {vitals.map((v, i) => {
        const t = trend(v);
        return (
          <span key={v.kind} className="inline-flex items-baseline whitespace-nowrap">
            {i > 0 && (
              <span aria-hidden="true" className="text-line-strong mx-1.5">
                ·
              </span>
            )}
            <span className="text-ink-3 mr-1 text-xs">{v.label}</span>
            <span className="text-ink font-medium tabular-nums">{formatVital(v)}</span>
            {t && (
              <span className="text-ink-3 ml-0.5 text-xs" title={`Was ${v.previous}`}>
                <span aria-hidden="true">{t === "up" ? "↑" : "↓"}</span>
                <span className="sr-only">
                  {t === "up" ? "up" : "down"} from {v.previous}
                </span>
              </span>
            )}
          </span>
        );
      })}
    </p>
  );
}

function Facts({ p, className = "" }: { p: HandoverPatient; className?: string }) {
  if (p.symptoms.length === 0 && p.medications.length === 0 && p.open_drafts === 0) return null;
  return (
    <ul className={`text-ink-2 flex flex-wrap gap-x-4 gap-y-1.5 text-sm ${className}`}>
      {p.symptoms.length > 0 && (
        <li className="inline-flex items-center gap-1.5">
          <span className="text-ink-3 text-xs font-medium">Reports</span>
          {p.symptoms.join(", ")}
        </li>
      )}
      {p.medications.map((m, i) => (
        <li key={i} className="inline-flex items-center gap-1.5">
          <PillIcon size={13} className="text-ink-3" />
          {[m.name, m.dose, m.route].filter(Boolean).join(" ")}
        </li>
      ))}
      {p.open_drafts > 0 && (
        <li className="inline-flex items-center gap-1.5">
          <FileIcon size={13} className="text-ink-3" />
          {p.open_drafts} draft{p.open_drafts > 1 ? "s" : ""} awaiting review
          <Link
            href="/ward"
            className="text-brand-text focus-visible:outline-brand-ring rounded font-medium hover:underline focus-visible:outline-2 print:hidden"
          >
            Review
          </Link>
        </li>
      )}
    </ul>
  );
}

function Identity({ p }: { p: HandoverPatient }) {
  return (
    <>
      <span className="bg-surface-3 text-ink-2 ring-line shrink-0 rounded-md px-2 py-1 font-mono text-xs font-semibold ring-1 ring-inset">
        {p.room}
      </span>
      <Link
        href={`/patients/${p.patient_id}`}
        className="text-ink hover:text-brand-text focus-visible:outline-brand-ring group inline-flex min-w-0 items-center gap-1 rounded font-semibold tracking-[-0.01em] focus-visible:outline-2"
      >
        <span className="truncate">
          {p.family_name}, {p.given_name}
        </span>
        <ChevronRightIcon
          size={14}
          className="text-ink-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 print:hidden"
        />
      </Link>
    </>
  );
}

/** Flagged patient: tiles for what needs attention, the rest in one quiet line. */
function AttentionCard({ p }: { p: HandoverPatient }) {
  const meta = PRIORITY[p.priority];
  const chips = mergeBloodPressure(p.vitals);
  const flagged = chips.filter(needsAttention);
  const quiet = chips.filter((v) => !needsAttention(v));
  return (
    <li className="card overflow-hidden print:break-inside-avoid print:shadow-none">
      <div className="border-line bg-surface-2/70 flex items-center gap-3 border-b px-4 py-2.5 sm:px-5 print:bg-transparent">
        <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${meta.dot}`} />
        <Identity p={p} />
        <span className="flex-1" />
        <Pill tone={meta.tone}>
          <PriorityIcon priority={p.priority} />
          {meta.label}
        </Pill>
      </div>
      <div className="p-4 sm:p-5">
        {flagged.length > 0 && (
          <ul
            className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
            aria-label="Values that need attention"
          >
            {flagged.map((v) => (
              <VitalTile key={v.kind} v={v} />
            ))}
          </ul>
        )}
        {quiet.length > 0 && (
          <div className={flagged.length > 0 ? "mt-3" : ""}>
            <QuietVitals vitals={quiet} lead="Otherwise" />
          </div>
        )}
        <p className="text-ink mt-4 text-[15px] leading-relaxed">{p.summary}</p>
        <Facts p={p} className="border-line mt-4 border-t pt-3" />
      </div>
    </li>
  );
}

/** Patient without flagged values: one row, values inline. */
function CompactRow({ p }: { p: HandoverPatient }) {
  const chips = mergeBloodPressure(p.vitals);
  return (
    <li className="flex flex-col gap-2 px-4 py-3.5 sm:px-5 print:break-inside-avoid">
      <div className="flex min-w-0 items-center gap-3">
        <Identity p={p} />
      </div>
      {chips.length > 0 ? (
        <QuietVitals vitals={chips} />
      ) : (
        <p className="text-ink-3 text-sm">No confirmed observations this shift.</p>
      )}
      <Facts p={p} />
    </li>
  );
}

function PriorityBar({ h }: { h: Handover }) {
  const total = h.patients.length;
  const keys = ["critical", "warning", "review", "stable"] as const;
  return (
    <div>
      <div
        className="bg-surface-3 flex h-2 gap-0.5 overflow-hidden rounded-full print:hidden"
        aria-hidden="true"
      >
        {keys.map((k) => {
          const n = h.counts[k] ?? 0;
          if (!n || !total) return null;
          return (
            <span
              key={k}
              className={`${PRIORITY[k].dot} h-full rounded-full transition-[flex-basis] duration-300`}
              style={{ flexBasis: `${(n / total) * 100}%` }}
            />
          );
        })}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Patients by priority">
        {keys.map((k) => {
          const n = h.counts[k] ?? 0;
          const section = SECTIONS.find((s) => s.match.includes(k));
          const body = (
            <>
              <span
                aria-hidden="true"
                className={`size-2.5 shrink-0 rounded-full ${n ? PRIORITY[k].dot : "bg-line-strong"}`}
              />
              <span
                className={`text-lg font-semibold tabular-nums ${n ? "text-ink" : "text-ink-3"}`}
              >
                {n}
              </span>
              <span className="text-ink-3 truncate text-xs">{PRIORITY[k].label}</span>
            </>
          );
          return (
            <li key={k}>
              {n && section ? (
                <a
                  href={`#${section.id}`}
                  className="bg-surface ring-line hover:ring-line-strong focus-visible:outline-brand-ring flex items-center gap-2.5 rounded-xl px-3 py-2.5 ring-1 transition-shadow focus-visible:outline-2 print:ring-0"
                >
                  {body}
                </a>
              ) : (
                <div className="bg-surface ring-line flex items-center gap-2.5 rounded-xl px-3 py-2.5 ring-1 print:ring-0">
                  {body}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Phone and tablet: jump between sections without scrolling past every card. */
function SectionNav({ h }: { h: Handover }) {
  const items = SECTIONS.map((s) => ({
    ...s,
    n: h.patients.filter((p) => s.match.includes(p.priority)).length,
  })).filter((s) => s.n > 0);
  if (items.length < 2) return null;
  return (
    <nav
      aria-label="Sections"
      className="bg-surface/90 border-line sticky top-(--topbar) z-10 -mx-4 -mt-4 border-b px-4 py-2 backdrop-blur sm:-mx-5 sm:px-5 lg:hidden print:hidden"
    >
      <ul className="flex [scrollbar-width:none] gap-2 overflow-x-auto">
        {items.map((s) => (
          <li key={s.id} className="min-w-0 flex-1">
            <a
              href={`#${s.id}`}
              className="bg-surface-2 text-ink-2 ring-line hover:text-ink focus-visible:outline-brand-ring flex items-center justify-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ring-1 ring-inset focus-visible:outline-2"
            >
              <span
                aria-hidden="true"
                className={`size-2 rounded-full ${PRIORITY[s.match[0] ?? "stable"].dot}`}
              />
              {s.short}
              <span className="text-ink-3 tabular-nums">{s.n}</span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function HandoverPage() {
  const [params, setParams] = useUrlState();
  const hours = Number(params.get("hours") ?? 12) || 12;
  const handover = useHandover(hours);
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const canShare = useSyncExternalStore(
    () => () => {},
    () => typeof navigator.share === "function",
    () => false,
  );
  usePageTitle("Shift handover");
  const h = handover.data;

  async function copy() {
    if (!h) return;
    try {
      await navigator.clipboard.writeText(handoverText(h));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast({
        title: "Handover copied",
        description: "Paste it into a message or the handover sheet.",
      });
    } catch {
      toast({ title: "Could not copy", tone: "danger" });
    }
  }

  async function share() {
    if (!h) return;
    try {
      await navigator.share({ title: `Ward ${h.ward} handover`, text: handoverText(h) });
    } catch {
      // The nurse closed the share sheet.
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Shift handover"
        title={h ? `Ward ${h.ward} handover` : "Shift handover"}
        subtitle={
          h
            ? `Last ${h.hours} hours · ${formatDateTime(h.until)} · built from nurse-confirmed values only`
            : "Built from nurse-confirmed values only"
        }
        actions={
          <div className="flex flex-wrap items-center gap-2 print:hidden">
            <Select
              size="sm"
              title="Shift length"
              aria-label="Shift length"
              className="w-36"
              value={String(hours)}
              onChange={(v) => setParams({ hours: v === "12" ? null : v })}
              options={WINDOWS.map((w) => ({ value: String(w), label: `Last ${w} hours` }))}
            />
            <Button variant="secondary" size="sm" onClick={() => void copy()} disabled={!h}>
              {copied ? <CheckIcon size={15} /> : <CopyIcon size={15} />}
              {copied ? "Copied" : "Copy text"}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => window.print()} disabled={!h}>
              <PrinterIcon size={15} />
              Print
            </Button>
            {canShare && (
              <Button
                variant="secondary"
                size="sm"
                className="lg:hidden"
                onClick={() => void share()}
                disabled={!h}
              >
                <UploadIcon size={15} />
                Share
              </Button>
            )}
          </div>
        }
      />

      {handover.isPending && (
        <SkeletonStatus label="Building the handover…">
          <CardSkeleton lines={3} />
          <div className="mt-4 grid gap-3">
            <CardSkeleton lines={3} />
            <CardSkeleton lines={3} />
          </div>
        </SkeletonStatus>
      )}
      {handover.isError && <ErrorState error={handover.error} />}

      {h && (
        <div aria-busy={handover.isPlaceholderData} className="flex flex-col gap-8">
          <Card className="from-brand-soft/60 to-surface overflow-hidden bg-gradient-to-br p-5 sm:p-6 print:bg-none print:shadow-none">
            <div className="flex items-start gap-3">
              <span className="bg-surface text-brand-text ring-brand/15 flex size-9 shrink-0 items-center justify-center rounded-xl ring-1 print:hidden">
                <ClipboardIcon size={17} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-ink text-[15px] leading-relaxed sm:text-base">{h.summary}</p>
                <p className="text-ink-3 mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <span className="inline-flex items-center gap-1.5">
                    <SparkIcon size={12} />
                    {h.written_by === "rules"
                      ? "Written from the confirmed values by rule. No AI is involved in this text."
                      : `Written by ${h.written_by} from the confirmed values, with rooms only, never names.`}
                  </span>
                  <span className="tabular-nums">
                    Shift window {formatTime(h.since)} – {formatTime(h.until)}
                  </span>
                </p>
              </div>
            </div>
            <div className="mt-5">
              <PriorityBar h={h} />
            </div>
            {h.unassigned_drafts > 0 && (
              <p className="text-ink-2 mt-3 text-sm">
                {h.unassigned_drafts} draft{h.unassigned_drafts > 1 ? "s" : ""} on the ward still
                need a patient.{" "}
                <Link
                  href="/ward"
                  className="text-brand-text font-medium hover:underline print:hidden"
                >
                  Open the ward
                </Link>
              </p>
            )}
          </Card>

          <SectionNav h={h} />

          {h.patients.length === 0 && <EmptyState title="No patients on this ward." />}
          {SECTIONS.map((section) => {
            const rows = h.patients.filter((p) => section.match.includes(p.priority));
            if (rows.length === 0) return null;
            const compact = section.id !== "needs-attention";
            return (
              <section
                key={section.id}
                id={section.id}
                aria-labelledby={`h-${section.id}`}
                className="scroll-mt-[calc(var(--topbar)+3.5rem)] lg:scroll-mt-[calc(var(--topbar)+1.5rem)]"
              >
                <div className="mb-3 flex items-baseline gap-3">
                  <h2
                    id={`h-${section.id}`}
                    className="text-ink flex items-center gap-2.5 text-lg font-semibold tracking-[-0.01em]"
                  >
                    <span
                      aria-hidden="true"
                      className={`size-2.5 rounded-full ${PRIORITY[section.match[0] ?? "stable"].dot}`}
                    />
                    {section.title}
                    <span className="text-ink-3 text-sm font-normal tabular-nums">
                      {rows.length}
                    </span>
                  </h2>
                  <p className="text-ink-3 hidden text-sm sm:block">{section.hint}</p>
                </div>
                {compact ? (
                  <ul className="card divide-line divide-y print:shadow-none">
                    {rows.map((p) => (
                      <CompactRow key={p.patient_id} p={p} />
                    ))}
                  </ul>
                ) : (
                  <ul className="flex flex-col gap-3">
                    {rows.map((p) => (
                      <AttentionCard key={p.patient_id} p={p} />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
          <p className="text-ink-3 hidden text-xs print:block">
            Synthetic demo data. Built from nurse-confirmed values only; no diagnosis or treatment
            advice.
          </p>
        </div>
      )}
    </>
  );
}
