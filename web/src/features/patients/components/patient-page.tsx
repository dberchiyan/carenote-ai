"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

const MOBILE_ROWS = 30;

import { TrendChart } from "@/shared/charts/trend-chart";
import { FlagBadge } from "@/shared/ui/flag-badge";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Select } from "@/shared/ui/field";
import { ActivityIcon, DownloadIcon } from "@/shared/ui/icons";
import { CardSkeleton, Skeleton, SkeletonStatus, TableSkeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState, PageHeader, Pill } from "@/shared/ui/states";
import { useToast } from "@/shared/ui/toast";
import { markGuideStep } from "@/features/guide/hooks";
import type { VitalKind } from "@/shared/api/types";
import { ageFrom, formatDateTime, initials } from "@/shared/lib/format";
import { patientsApi, useObservations, usePatient, useRules } from "@/features/patients/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";
import { FLAG_META, isFlag, isVitalKind, VITAL_KINDS, VITAL_LABELS } from "@/shared/lib/vitals";

export function PatientPage() {
  const { id } = useParams<{ id: string }>();
  const patient = usePatient(id);
  const [days, setDays] = useState(30);
  const [showAll, setShowAll] = useState(false);
  const observations = useObservations(id, days);
  const rules = useRules();
  const [kind, setKind] = useState<VitalKind | null>(null);
  const [exportError, setExportError] = useState<Error | null>(null);
  const [exporting, setExporting] = useState(false);
  const toast = useToast();
  usePageTitle(
    patient.data ? `${patient.data.family_name}, ${patient.data.given_name}` : undefined,
  );

  const kinds = useMemo(
    () => VITAL_KINDS.filter((k) => observations.data?.items.some((o) => o.kind === k)),
    [observations.data],
  );
  const selected = kind ?? kinds[0] ?? null;
  const rows = observations.data?.items ?? [];
  const points = rows
    .filter((o) => o.kind === selected)
    .map((o) => ({
      at: o.effective_at,
      value: o.value,
      flag: isFlag(o.flag) ? o.flag : ("normal" as const),
    }));
  const threshold = selected ? rules.data?.rules[selected] : undefined;

  if (patient.isPending) {
    return (
      <SkeletonStatus label="Loading patient…">
        <Skeleton className="mb-3 h-3 w-28" />
        <Skeleton className="h-9 w-72" />
        <Skeleton className="mt-3 h-4 w-96 max-w-full" />
        <div className="mt-8 grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }, (_, i) => (
            <CardSkeleton key={i} lines={1} />
          ))}
        </div>
        <div className="mt-6">
          <CardSkeleton lines={4} />
        </div>
      </SkeletonStatus>
    );
  }
  if (patient.isError) return <ErrorState error={patient.error} />;
  const p = patient.data;

  async function onExport() {
    setExporting(true);
    setExportError(null);
    try {
      await patientsApi.downloadFhir(p.id, p.mrn);
      markGuideStep("fhir-exported");
      toast({
        title: "FHIR bundle downloaded",
        description: `Patient and confirmed observations for MRN ${p.mrn}.`,
      });
    } catch (e) {
      setExportError(e instanceof Error ? e : new Error("Export failed"));
    } finally {
      setExporting(false);
    }
  }

  const latest = kinds.map((k) => {
    const ofKind = rows.filter((o) => o.kind === k);
    return { kind: k, row: ofKind[ofKind.length - 1], count: ofKind.length };
  });

  return (
    <>
      <PageHeader
        eyebrow="Patient record"
        title={`${p.family_name}, ${p.given_name}`}
        subtitle={`Ward ${p.ward} · Room ${p.room} · ${ageFrom(p.birth_date)} y · ${p.sex} · MRN ${p.mrn} (synthetic)`}
        actions={
          <Button variant="secondary" onClick={onExport} disabled={exporting}>
            <DownloadIcon size={16} />
            {exporting ? "Exporting…" : "Export FHIR"}
          </Button>
        }
      />
      <div className="-mt-2 mb-8 flex flex-wrap items-center gap-2">
        <span
          aria-hidden="true"
          className="bg-brand-soft text-brand-text ring-brand/15 mr-1 flex size-10 items-center justify-center rounded-full text-sm font-semibold ring-1"
        >
          {initials(`${p.given_name} ${p.family_name}`)}
        </span>
        <Pill tone="neutral">Room {p.room}</Pill>
        <Pill tone="neutral">{ageFrom(p.birth_date)} years</Pill>
        <Pill tone="neutral">{p.sex === "female" ? "Female" : "Male"}</Pill>
        <Pill tone="brand">HL7 FHIR R4 ready</Pill>
      </div>
      {exportError && (
        <div className="mb-4">
          <ErrorState error={exportError} />
        </div>
      )}

      {observations.isPending && (
        <SkeletonStatus label="Loading observations…">
          <TableSkeleton rows={6} columns={6} />
        </SkeletonStatus>
      )}
      {observations.isError && <ErrorState error={observations.error} />}
      {observations.data?.total === 0 && (
        <EmptyState
          icon={<ActivityIcon />}
          title={`No confirmed observations in the last ${days} days.`}
        >
          Values appear here after a nurse confirms a voice-note draft for this patient.
          <span className="mt-3 block">
            <DaysSelect value={days} onChange={setDays} />
          </span>
        </EmptyState>
      )}

      {latest.length > 0 && (
        <section aria-label="Latest values" className="mb-6">
          <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4 xl:grid-cols-6">
            {latest.map(({ kind: k, row, count }) => {
              const flag = row && isFlag(row.flag) ? row.flag : "normal";
              const active = k === selected;
              return (
                <li key={k}>
                  <button
                    type="button"
                    aria-pressed={active}
                    onClick={() => setKind(k)}
                    className={`card focus-visible:outline-brand-ring flex h-full w-full flex-col items-start gap-1 p-4 text-left transition-[box-shadow,border-color] focus-visible:outline-2 focus-visible:outline-offset-2 ${
                      active
                        ? "border-brand/50 shadow-[0_0_0_3px_color-mix(in_oklab,var(--brand-ring)_14%,transparent)]"
                        : "hover:border-line-strong"
                    }`}
                  >
                    <span className="flex w-full items-baseline justify-between gap-2">
                      <span className="text-ink-3 text-xs font-medium">
                        {VITAL_LABELS[k].label}
                      </span>
                      <span className="text-ink-3 text-[11px] whitespace-nowrap tabular-nums">
                        {count}×
                      </span>
                    </span>
                    <span className="flex items-baseline gap-1">
                      <span className="text-ink text-[1.625rem] leading-none font-semibold tracking-[-0.03em] tabular-nums">
                        {row?.value}
                      </span>
                      <span className="text-ink-3 text-xs">{VITAL_LABELS[k].unit}</span>
                    </span>
                    <span className="mt-1">
                      {flag !== "normal" ? (
                        <FlagBadge flag={flag} />
                      ) : (
                        <span className="text-ink-3 text-xs">{FLAG_META.normal.label}</span>
                      )}
                    </span>
                    <span className="sr-only">
                      {count} reading{count > 1 ? "s" : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {selected && points.length > 0 && (
        <Card className="mb-6 p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[15px] font-semibold tracking-[-0.01em]">
              {VITAL_LABELS[selected].label} trend{" "}
              <span className="text-ink-3 font-normal">({VITAL_LABELS[selected].unit})</span>
            </h2>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <span className="text-ink-2 whitespace-nowrap">Vital sign</span>
                <Select
                  size="sm"
                  title="Vital sign"
                  className="w-44"
                  value={selected}
                  onChange={(k) => setKind(k)}
                  options={kinds.map((k) => ({
                    value: k,
                    label: VITAL_LABELS[k].label,
                    hint: VITAL_LABELS[k].unit,
                  }))}
                />
              </label>
              <DaysSelect value={days} onChange={setDays} />
            </div>
          </div>
          <TrendChart
            points={points}
            unit={VITAL_LABELS[selected].unit}
            label={VITAL_LABELS[selected].label}
            normal={
              threshold
                ? {
                    low: threshold.warning_below ?? undefined,
                    high: threshold.warning_above ?? undefined,
                  }
                : undefined
            }
          />
        </Card>
      )}

      {observations.data && rows.length > 0 && (
        <section aria-label="Confirmed observations" className="md:hidden">
          <h2 className="mb-2 text-[15px] font-semibold">
            Confirmed observations
            <span className="text-ink-3 ml-2 text-xs font-normal">last {days} days</span>
          </h2>
          <ul className="card divide-line divide-y">
            {[...rows]
              .reverse()
              .slice(0, showAll ? rows.length : MOBILE_ROWS)
              .map((o) => (
                <li key={o.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="text-ink block text-sm font-medium">
                      {isVitalKind(o.kind) ? VITAL_LABELS[o.kind].label : o.kind}
                    </span>
                    <span className="text-ink-3 block text-xs">
                      {formatDateTime(o.effective_at)}
                    </span>
                  </span>
                  <span className="text-ink text-right font-semibold tabular-nums">
                    {o.value}
                    <span className="text-ink-3 ml-1 text-xs font-normal">
                      {isVitalKind(o.kind) ? VITAL_LABELS[o.kind].unit : o.unit}
                    </span>
                  </span>
                  {isFlag(o.flag) && o.flag !== "normal" && <FlagBadge flag={o.flag} compact />}
                </li>
              ))}
          </ul>
          {rows.length > MOBILE_ROWS && !showAll && (
            <Button
              variant="secondary"
              size="sm"
              className="mt-3 w-full"
              onClick={() => setShowAll(true)}
            >
              Show all {rows.length}
            </Button>
          )}
        </section>
      )}
      {observations.data && rows.length > 0 && (
        <Card className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[640px] text-left text-sm">
            <caption className="px-5 pt-5 pb-3 text-left text-[15px] font-semibold">
              Confirmed observations
              <span className="text-ink-3 ml-2 text-xs font-normal">
                {rows.length < observations.data.total
                  ? `first ${rows.length} of ${observations.data.total} in the last ${days} days`
                  : `last ${days} days`}
              </span>
            </caption>
            <thead className="border-line bg-surface-2 text-ink-3 border-b text-xs">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">
                  Time
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Vital sign
                </th>
                <th scope="col" className="px-5 py-3 text-right font-medium">
                  Value
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Unit (UCUM)
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  LOINC
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Flag
                </th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((o) => (
                <tr key={o.id} className="border-line hover:bg-surface-2 border-b last:border-0">
                  <td className="px-5 py-3 whitespace-nowrap">{formatDateTime(o.effective_at)}</td>
                  <td className="px-5 py-3">
                    {isVitalKind(o.kind) ? VITAL_LABELS[o.kind].label : o.kind}
                  </td>
                  <td className="px-5 py-3 text-right font-medium tabular-nums">{o.value}</td>
                  <td className="px-5 py-3 font-mono text-xs">{o.unit}</td>
                  <td className="px-5 py-3 font-mono text-xs">{o.code}</td>
                  <td className="px-5 py-3">{isFlag(o.flag) && <FlagBadge flag={o.flag} />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

const WINDOWS = [7, 30, 90, 365];

function DaysSelect({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-ink-2 whitespace-nowrap">Period</span>
      <Select
        size="sm"
        title="Period"
        className="w-40"
        value={String(value)}
        onChange={(d) => onChange(Number(d))}
        options={WINDOWS.map((d) => ({ value: String(d), label: `Last ${d} days` }))}
      />
    </label>
  );
}
