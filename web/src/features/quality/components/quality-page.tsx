"use client";

import { useState } from "react";

import { buttonClass } from "@/shared/ui/button";
import { Card, CardHeader } from "@/shared/ui/card";
import {
  ActivityIcon,
  AlertIcon,
  DownloadIcon,
  EditIcon,
  FileIcon,
  ShieldIcon,
  TargetIcon,
  UsersIcon,
} from "@/shared/ui/icons";
import { StatCard } from "@/shared/ui/stat";
import { CardSkeleton, StatCardsSkeleton, SkeletonStatus } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState, PageHeader, Pill } from "@/shared/ui/states";
import type { Corrections, EvalRun, FieldChange } from "@/shared/api/types";
import { formatDateTime } from "@/shared/lib/format";
import { useCorrections, useEvalRuns } from "@/features/quality/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";
import { markGuideStep } from "@/features/guide/hooks";
import { isVitalKind, VITAL_LABELS } from "@/shared/lib/vitals";

const DAYS = 30;

const DATASETS: Record<string, { label: string; description: string }> = {
  cases_holdout: {
    label: "Held-out set",
    description:
      "Hand-written dictations in phrasing the extractor was never written for. Measures generalisation.",
  },
  cases: {
    label: "Template set",
    description:
      "Generated from the same templates the rule-based extractor was written against. Measures the harness end to end, not real-world accuracy.",
  },
  cases_paraphrased: {
    label: "Paraphrased set",
    description: "Template cases rewritten by an LLM into freer phrasing.",
  },
  cases_corrections: {
    label: "Nurse corrections",
    description: "Cases exported from notes that nurses corrected before confirming.",
  },
};

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1)}`);

function fieldLabel(field: string) {
  if (isVitalKind(field)) return VITAL_LABELS[field].label;
  return field === "symptom" ? "Symptom" : field === "medication" ? "Medication" : field;
}

function describeChange(c: FieldChange) {
  if (c.change === "added") return `added ${c.after}`;
  if (c.change === "removed") return `removed ${c.before}`;
  return `${c.before} → ${c.after}`;
}

/** Horizontal meter. The number is always printed; the bar only reinforces it. */
function Meter({ value, max = 1 }: { value: number; max?: number }) {
  return (
    <span
      aria-hidden="true"
      className="bg-surface-3 block h-1.5 w-full overflow-hidden rounded-full"
    >
      <span
        className="block h-full rounded-full bg-[var(--chart-series)]"
        style={{ width: `${Math.max(2, (value / max) * 100)}%` }}
      />
    </span>
  );
}

function EvalSection({ runs }: { runs: EvalRun[] }) {
  const ordered = [...runs].sort(
    (a, b) =>
      Object.keys(DATASETS).indexOf(a.dataset) - Object.keys(DATASETS).indexOf(b.dataset) ||
      a.provider.localeCompare(b.provider),
  );
  const [selected, setSelected] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const run = ordered[Math.min(selected, ordered.length - 1)];
  if (!run) return null;
  const meta = DATASETS[run.dataset] ?? { label: run.dataset, description: "" };
  const misses = run.cases.filter((c) => !c.perfect);
  const tags = [...run.by_tag].sort(
    (a, b) => (a.value_accuracy ?? 1) - (b.value_accuracy ?? 1) || b.cases - a.cases,
  );
  const template = runs.find((r) => r.dataset === "cases" && r.model === run.model);
  const s = run.summary;

  return (
    <section aria-labelledby="evals-heading" className="mb-12">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="evals-heading" className="text-lg font-semibold tracking-[-0.01em]">
            Offline evaluation
          </h2>
          <p className="text-ink-3 mt-0.5 text-sm">
            The real pipeline (matching, redaction, extraction, validation, flags) run on synthetic
            dictations with known answers.
          </p>
        </div>
        <div
          role="group"
          aria-label="Eval dataset"
          className="bg-surface-3 flex flex-wrap gap-1 rounded-xl p-1"
        >
          {ordered.map((r, i) => (
            <button
              key={r.report + r.dataset}
              type="button"
              aria-pressed={i === selected}
              onClick={() => {
                setSelected(i);
                setShowAll(false);
              }}
              className={`focus-visible:outline-brand-ring rounded-lg px-3 py-1.5 text-sm font-medium focus-visible:outline-2 ${
                i === selected
                  ? "bg-surface text-ink shadow-[0_1px_2px_rgb(15_23_42/0.08),0_0_0_1px_var(--line)]"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              {DATASETS[r.dataset]?.label ?? r.dataset}
              {runs.some((o) => o.dataset === r.dataset && o.model !== r.model) && (
                <span className="text-ink-3 font-normal"> · {r.model}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <p className="text-ink-2 mb-4 text-sm">
        <span className="text-ink font-medium">{meta.label}:</span> {meta.description}{" "}
        <span className="text-ink-3">
          {s.cases} cases · model <span className="font-mono text-xs">{run.model}</span> · prompt{" "}
          <span className="font-mono text-xs">{run.prompt_version}</span> · {run.date}
        </span>
      </p>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard
          icon={<TargetIcon size={16} />}
          label="Value accuracy"
          value={pct(s.value_accuracy)}
          unit="%"
          hint="Expected vital values extracted exactly"
        />
        <StatCard
          icon={<FileIcon size={16} />}
          label="Perfect cases"
          value={`${s.perfect_cases}/${s.cases}`}
          hint="Every field right, nothing extra"
        />
        <StatCard
          icon={<UsersIcon size={16} />}
          label="Patient match"
          value={pct(s.patient_match_accuracy)}
          unit="%"
          hint="Right patient, or the nurse is asked"
        />
        <StatCard
          icon={<ShieldIcon size={16} />}
          label="Vital precision"
          value={pct(s.vital_precision)}
          unit="%"
          hint="Extracted vitals that were really said"
        />
      </div>

      {template && run.dataset === "cases_holdout" && template.summary.value_accuracy != null && (
        <div
          role="note"
          className="border-line bg-surface mb-6 flex gap-3 rounded-xl border px-4 py-3 text-sm"
        >
          <AlertIcon size={17} className="text-brand-text mt-0.5 shrink-0" />
          <p className="text-ink-2">
            <span className="text-ink font-medium">
              {pct(template.summary.value_accuracy)}% on the template set, {pct(s.value_accuracy)}%
              here.
            </span>{" "}
            The template score measured the harness, not the extractor. Misses below are mostly
            values left out (the nurse sees an empty field), not wrong values.
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card className="p-6">
          <CardHeader
            icon={<ActivityIcon size={17} />}
            title="By tag"
            description="Value accuracy per kind of difficulty, weakest first."
          />
          <ul className="flex flex-col gap-3.5">
            {tags.map((t) => (
              <li key={t.tag}>
                <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                  <span className="text-ink font-medium">{t.tag.replaceAll("_", " ")}</span>
                  <span className="text-ink-3 text-xs tabular-nums">
                    <span className="text-ink text-sm font-semibold">
                      {pct(t.value_accuracy)}
                      {t.value_accuracy != null && "%"}
                    </span>{" "}
                    · {t.perfect_cases}/{t.cases} perfect
                  </span>
                </div>
                <Meter value={t.value_accuracy ?? 0} />
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-6">
          <CardHeader
            icon={<AlertIcon size={17} />}
            title={`Where it fails (${misses.length})`}
            description="Imperfect cases with what was expected and what came out."
          />
          {misses.length === 0 ? (
            <p className="text-ink-3 text-sm">Every case is perfect on this dataset.</p>
          ) : (
            <ul className="divide-line flex flex-col divide-y">
              {(showAll ? misses : misses.slice(0, 6)).map((c) => (
                <li key={c.case_id} className="py-3.5 first:pt-0">
                  <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                    <span className="text-ink-3 font-mono text-xs">{c.case_id}</span>
                    {c.tags.map((t) => (
                      <Pill key={t}>{t.replaceAll("_", " ")}</Pill>
                    ))}
                  </div>
                  <p className="text-ink text-sm leading-relaxed">“{c.text}”</p>
                  <ul className="mt-1.5 flex flex-col gap-0.5">
                    {(c.error ? [c.error] : c.diffs).map((d) => (
                      <li key={d} className="text-ink-2 font-mono text-xs">
                        <span aria-hidden="true" className="text-red-600 dark:text-red-400">
                          ✕{" "}
                        </span>
                        {d}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
          {misses.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="text-brand-text focus-visible:outline-brand-ring mt-3 rounded text-sm font-medium hover:underline focus-visible:outline-2"
            >
              {showAll ? "Show fewer" : `Show all ${misses.length}`}
            </button>
          )}
        </Card>
      </div>
    </section>
  );
}

function CorrectionsSection({ data }: { data: Corrections }) {
  const top = data.by_field[0];
  const max = Math.max(1, ...data.by_field.map((f) => f.total));
  return (
    <section aria-labelledby="corrections-heading">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="corrections-heading" className="text-lg font-semibold tracking-[-0.01em]">
            Nurse corrections
          </h2>
          <p className="text-ink-3 mt-0.5 text-sm">
            Every edit before Confirm is ground truth: the nurse heard the dictation. Last {DAYS}{" "}
            days{data.ward ? `, ward ${data.ward}` : ", all wards"}.
          </p>
        </div>
        <a
          href={`/api/quality/corrections/export?days=${DAYS}`}
          download="cases_corrections.jsonl"
          onClick={() => markGuideStep("eval-exported")}
          className={buttonClass("secondary")}
        >
          <DownloadIcon size={16} />
          Export as eval cases
        </a>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard
          icon={<EditIcon size={16} />}
          label="Edit rate"
          value={pct(data.edit_rate)}
          unit="%"
          hint="Confirmed notes the nurse corrected"
        />
        <StatCard
          icon={<FileIcon size={16} />}
          label="Corrected notes"
          value={String(data.edited_notes)}
          hint={`Of ${data.confirmed_notes} confirmed`}
        />
        <StatCard
          icon={<TargetIcon size={16} />}
          label="Most corrected"
          value={top ? fieldLabel(top.field) : "—"}
          hint={top ? `${top.total} corrections` : "No corrections yet"}
        />
        <StatCard
          icon={<ShieldIcon size={16} />}
          label="Confirmed without edits"
          value={pct(data.edit_rate == null ? null : 1 - data.edit_rate)}
          unit="%"
          hint="AI draft accepted as is"
        />
      </div>

      {data.edited_notes === 0 ? (
        <EmptyState icon={<EditIcon />} title="No corrected notes in this period." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Card className="p-6">
            <CardHeader
              icon={<ActivityIcon size={17} />}
              title="Corrected fields"
              description="What the model gets wrong in use."
            />
            <ul className="flex flex-col gap-3.5">
              {data.by_field.map((f) => (
                <li key={f.field}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                    <span className="text-ink font-medium">{fieldLabel(f.field)}</span>
                    <span className="text-ink-3 text-xs tabular-nums">
                      <span className="text-ink text-sm font-semibold">{f.total}</span>
                      {f.added > 0 && ` · ${f.added} added`}
                      {f.changed > 0 && ` · ${f.changed} changed`}
                      {f.removed > 0 && ` · ${f.removed} removed`}
                    </span>
                  </div>
                  <Meter value={f.total} max={max} />
                </li>
              ))}
            </ul>
          </Card>
          <Card className="p-6">
            <CardHeader
              icon={<EditIcon size={17} />}
              title="Recent corrections"
              description="Transcripts are shown redacted, as the model saw them."
            />
            <ul className="divide-line flex flex-col divide-y">
              {data.recent.map((n) => (
                <li key={n.note_id} className="py-3.5 first:pt-0">
                  <div className="text-ink-3 mb-1 flex flex-wrap gap-x-2 text-xs">
                    <span>{formatDateTime(n.created_at)}</span>
                    {n.model && <span className="font-mono">{n.model}</span>}
                  </div>
                  <p className="text-ink text-sm leading-relaxed">“{n.redacted_transcript}”</p>
                  <ul className="mt-1.5 flex flex-wrap gap-1.5">
                    {n.changes.map((c, i) => (
                      <li
                        key={i}
                        className="bg-surface-2 ring-line text-ink-2 rounded-md px-2 py-0.5 text-xs ring-1 ring-inset"
                      >
                        <span className="text-ink font-medium">{fieldLabel(c.field)}</span>{" "}
                        <span className="tabular-nums">{describeChange(c)}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
      <p className="text-ink-3 mt-4 text-xs leading-relaxed">
        Exported cases keep the redacted text. Save the file as{" "}
        <code className="font-mono">api/evals/data/cases_corrections.jsonl</code> and run{" "}
        <code className="font-mono">make eval DATASET=cases_corrections</code>: today&apos;s
        mistakes become tomorrow&apos;s regression tests.
      </p>
    </section>
  );
}

export function QualityPage() {
  const evals = useEvalRuns();
  const corrections = useCorrections(DAYS);
  usePageTitle("AI quality");
  return (
    <>
      <PageHeader
        eyebrow="AI quality"
        title="AI quality"
        subtitle="Measured offline on synthetic dictations, and in use from what nurses correct."
      />
      {evals.isPending && (
        <SkeletonStatus label="Loading eval reports…">
          <StatCardsSkeleton />
          <CardSkeleton lines={6} />
        </SkeletonStatus>
      )}
      {evals.isError && <ErrorState error={evals.error} />}
      {evals.data?.length === 0 && <EmptyState title="No eval reports yet. Run `make eval`." />}
      {evals.data && evals.data.length > 0 && <EvalSection runs={evals.data} />}

      {corrections.isPending && (
        <SkeletonStatus label="Loading corrections…">
          <div className="mt-10">
            <StatCardsSkeleton />
          </div>
        </SkeletonStatus>
      )}
      {corrections.isError && <ErrorState error={corrections.error} />}
      {corrections.data && <CorrectionsSection data={corrections.data} />}
    </>
  );
}
