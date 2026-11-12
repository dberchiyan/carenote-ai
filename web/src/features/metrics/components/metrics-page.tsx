"use client";

import { useState } from "react";

import { ColumnChart } from "@/shared/charts/column-chart";
import { Card } from "@/shared/ui/card";
import { Select } from "@/shared/ui/field";
import { ActivityIcon, ClockIcon, FileIcon, SparkIcon } from "@/shared/ui/icons";
import { StatCard as Stat } from "@/shared/ui/stat";
import { StatCardsSkeleton, SkeletonStatus, TableSkeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState, PageHeader } from "@/shared/ui/states";
import type { DailyLlmMetrics } from "@/shared/api/types";
import { useLlmMetrics } from "@/features/metrics/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";

/** The keyless provider: costs nothing, and its token counts are an estimate (chars / 4). */
const RULE_BASED = "rule-based-v1";

const usd = (v: number) => (v === 0 ? "$0" : v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`);
const compact = (v: number) => new Intl.NumberFormat(undefined, { notation: "compact" }).format(v);

function byDay(rows: DailyLlmMetrics[]) {
  const days = new Map<string, { cost: number; tokens: number; extractions: number }>();
  for (const r of rows) {
    const d = days.get(r.day) ?? { cost: 0, tokens: 0, extractions: 0 };
    d.cost += r.cost_usd;
    d.tokens += r.input_tokens + r.output_tokens;
    d.extractions += r.extractions;
    days.set(r.day, d);
  }
  return [...days.entries()].map(([day, d]) => ({
    label: new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    }),
    ...d,
  }));
}

export function MetricsPage() {
  const [days, setDays] = useState(30);
  const metrics = useLlmMetrics(days);
  usePageTitle("LLM metrics");
  const data = metrics.data;
  const daily = data ? byDay(data.daily) : [];
  const latency =
    data && data.total_extractions
      ? data.daily.reduce((s, r) => s + r.avg_latency_ms * r.extractions, 0) /
        data.total_extractions
      : 0;

  return (
    <>
      <PageHeader
        eyebrow="Usage & cost"
        title="LLM metrics"
        subtitle={
          data?.ward ? `AI extractions on ward ${data.ward}` : "AI extractions on all wards"
        }
        actions={
          <label className="text-ink-2 flex items-center gap-2 text-sm">
            Period
            <Select
              size="sm"
              className="w-auto"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </Select>
          </label>
        }
      />
      {metrics.isPending && (
        <SkeletonStatus label="Loading metrics…">
          <StatCardsSkeleton />
          <TableSkeleton rows={5} columns={6} />
        </SkeletonStatus>
      )}
      {metrics.isError && <ErrorState error={metrics.error} />}
      {data && data.total_extractions === 0 && (
        <EmptyState title="No AI extractions in this period." />
      )}
      {data && data.total_extractions > 0 && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              icon={<FileIcon size={16} />}
              label="Extractions"
              value={compact(data.total_extractions)}
              hint={`AI drafts in the last ${days} days`}
            />
            <Stat
              icon={<SparkIcon size={16} />}
              label="Total cost"
              value={usd(data.total_cost_usd)}
              hint={
                data.transcription.notes > 0
                  ? `${usd(data.extraction_cost_usd)} extraction + ${usd(data.transcription.cost_usd)} transcription (${Math.round(data.transcription.seconds / 60)} min of audio)`
                  : "Provider list prices"
              }
            />
            <Stat
              icon={<ActivityIcon size={16} />}
              label="Cost per note"
              value={usd(data.avg_cost_per_note_usd)}
              hint="Average across all models"
            />
            <Stat
              icon={<ClockIcon size={16} />}
              label="Average latency"
              value={String(Math.round(latency))}
              unit="ms"
              hint="Extraction call, end to end"
            />
          </div>
          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <Card className="p-6">
              <h2 className="mb-4 text-[15px] font-semibold tracking-[-0.01em]">Cost per day</h2>
              <ColumnChart
                title="LLM cost per day in US dollars"
                format={usd}
                columns={daily.map((d) => ({
                  label: d.label,
                  value: d.cost,
                  detail: `${d.extractions} notes`,
                }))}
              />
            </Card>
            <Card className="p-6">
              <h2 className="mb-4 text-[15px] font-semibold tracking-[-0.01em]">
                Tokens per day
                {data.daily.some((r) => r.model === RULE_BASED) && (
                  <span className="text-ink-3 ml-2 text-xs font-normal">
                    estimated for the rule-based model
                  </span>
                )}
              </h2>
              <ColumnChart
                title="LLM tokens (input + output) per day"
                format={compact}
                columns={daily.map((d) => ({
                  label: d.label,
                  value: d.tokens,
                  detail: `${d.extractions} notes`,
                }))}
              />
            </Card>
          </div>
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <caption className="px-5 pt-5 pb-3 text-left text-[15px] font-semibold">
                By day and model
              </caption>
              <thead className="border-line bg-surface-2 text-ink-3 border-b text-xs">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Day (UTC)
                  </th>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Model
                  </th>
                  <th scope="col" className="px-5 py-3 text-right font-medium">
                    Notes
                  </th>
                  <th scope="col" className="px-5 py-3 text-right font-medium">
                    Input tokens
                  </th>
                  <th scope="col" className="px-5 py-3 text-right font-medium">
                    Output tokens
                  </th>
                  <th scope="col" className="px-5 py-3 text-right font-medium">
                    Cost
                  </th>
                  <th scope="col" className="px-5 py-3 text-right font-medium">
                    Avg / max latency
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.daily.map((r) => (
                  <tr
                    key={`${r.day}-${r.model}`}
                    className="border-line hover:bg-surface-2 border-b last:border-0"
                  >
                    <td className="px-5 py-3">{r.day}</td>
                    <td className="px-5 py-3 font-mono text-xs">
                      {r.model}
                      {r.model === RULE_BASED && (
                        <span
                          className="text-ink-3 ml-1 font-sans"
                          title="Token counts are estimated"
                        >
                          (est.)
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">{r.extractions}</td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {r.input_tokens.toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {r.output_tokens.toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">{usd(r.cost_usd)}</td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {Math.round(r.avg_latency_ms)} / {r.max_latency_ms} ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </>
  );
}
