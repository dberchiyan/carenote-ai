"use client";

import { useId, useState } from "react";

import { linear, niceTicks } from "@/shared/lib/scale";

export type Column = { label: string; value: number; detail?: string };

const W = 560;
const H = 200;
const M = { top: 20, right: 12, bottom: 32, left: 64 };

/** Single-series columns: <=24px wide, 4px rounded tops, one baseline, hover/focus tooltip. */
export function ColumnChart({
  columns,
  title,
  format,
}: {
  columns: Column[];
  title: string;
  format: (v: number) => string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const current = active === null ? null : columns[active];
  const titleId = useId();
  if (columns.length === 0) return null;
  const ticks = niceTicks(0, Math.max(...columns.map((c) => c.value), 0), 3);
  const top = ticks.at(-1) ?? 1;
  const y = linear([0, top], [H - M.bottom, M.top]);
  const base = H - M.bottom;
  const slot = (W - M.left - M.right) / columns.length;
  const bar = Math.min(24, slot * 0.6);

  return (
    <figure className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="group"
        aria-labelledby={titleId}
      >
        <title id={titleId}>{title}</title>
        <g aria-hidden="true">
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={M.left}
                x2={W - M.right}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--chart-grid)"
                strokeWidth={1}
              />
              <text
                x={M.left - 8}
                y={y(t)}
                dy="0.32em"
                textAnchor="end"
                className="fill-[var(--chart-axis)] text-[11px] tabular-nums"
              >
                {format(t)}
              </text>
            </g>
          ))}
        </g>
        {columns.map((c, i) => {
          const cx = M.left + slot * i + slot / 2;
          const h = Math.max(0, base - y(c.value));
          const x0 = cx - bar / 2;
          const yTop = base - h;
          const r = Math.min(4, bar / 2, h);
          const d =
            `M${x0},${base} V${yTop + r} Q${x0},${yTop} ${x0 + r},${yTop} ` +
            `H${x0 + bar - r} Q${x0 + bar},${yTop} ${x0 + bar},${yTop + r} V${base} Z`;
          return (
            <g
              key={c.label}
              tabIndex={0}
              role="img"
              aria-label={`${c.label}: ${format(c.value)}${c.detail ? `, ${c.detail}` : ""}`}
              onPointerEnter={() => setActive(i)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="outline-none"
            >
              <rect
                x={cx - slot / 2}
                y={M.top}
                width={slot}
                height={base - M.top}
                fill="transparent"
              />
              <path
                d={d}
                fill="var(--chart-series)"
                opacity={active === null || active === i ? 1 : 0.55}
              />
              <text
                x={cx}
                y={base + 18}
                textAnchor="middle"
                className="fill-[var(--chart-axis)] text-[11px]"
              >
                {c.label}
              </text>
            </g>
          );
        })}
      </svg>
      {current && active !== null && (
        <div
          role="status"
          className="border-line bg-surface shadow-lift pointer-events-none absolute top-0 w-40 rounded-xl border px-3 py-2 text-sm"
          style={{
            left: `clamp(0px, calc(${((M.left + slot * active + slot / 2) / W) * 100}% - 80px), calc(100% - 160px))`,
          }}
        >
          <div className="font-semibold tabular-nums">{format(current.value)}</div>
          <div className="text-ink-2">{current.label}</div>
          {current.detail && <div className="text-ink-2">{current.detail}</div>}
        </div>
      )}
    </figure>
  );
}
