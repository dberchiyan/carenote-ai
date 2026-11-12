"use client";

import { useId, useState } from "react";

import type { Flag } from "@/shared/api/types";
import { xTickIndices } from "@/shared/lib/chart-ticks";
import { formatDateTime } from "@/shared/lib/format";
import { linear, niceTicks } from "@/shared/lib/scale";
import { FLAG_META } from "@/shared/lib/vitals";

export type TrendPoint = { at: string; value: number; flag: Flag };

const W = 1000;
const H = 300;
const M = { top: 20, right: 88, bottom: 36, left: 48 };

/** Shaped marker centred on its point, with a surface-coloured halo so the line stops at its edge. */
function Marker({ flag, x, y, r }: { flag: Flag; x: number; y: number; r: number }) {
  const s = r + 2.5;
  const halo = { stroke: "var(--chart-surface)", strokeWidth: 3, paintOrder: "stroke" } as const;
  if (flag === "critical") {
    return (
      <polygon
        points={`${x},${y - s} ${x + s},${y} ${x},${y + s} ${x - s},${y}`}
        fill="var(--chart-critical)"
        {...halo}
      />
    );
  }
  if (flag === "warning") {
    // Equilateral-ish triangle whose centroid is the data point, not its base.
    const top = y - s * 1.1;
    const base = y + s * 0.65;
    return (
      <polygon
        points={`${x},${top} ${x + s},${base} ${x - s},${base}`}
        fill="var(--chart-warning)"
        {...halo}
      />
    );
  }
  return <circle cx={x} cy={y} r={r} fill="var(--chart-series)" {...halo} />;
}

/** One vital over time: 2px line, flagged points as shaped markers, the normal range as a band. */
export function TrendChart({
  points,
  unit,
  label,
  normal,
}: {
  points: TrendPoint[];
  unit: string;
  label: string;
  normal?: { low?: number; high?: number };
}) {
  const [active, setActive] = useState<number | null>(null);
  const titleId = useId();
  if (points.length === 0) return null;

  const times = points.map((p) => new Date(p.at).getTime());
  const values = points.map((p) => p.value);
  const lo = Math.min(...values, normal?.low ?? Infinity);
  const hi = Math.max(...values, normal?.high ?? -Infinity);
  const ticks = niceTicks(lo, hi, 4);
  const yMin = ticks[0] ?? lo;
  const yMax = ticks.at(-1) ?? hi;
  const y = linear([yMin, yMax], [H - M.bottom, M.top]);
  const x = linear([Math.min(...times), Math.max(...times)], [M.left + 16, W - M.right - 16]);
  const dots = points.map((p, i) => ({ ...p, x: x(times[i] ?? 0), y: y(p.value) }));
  const path = dots.map((d, i) => `${i ? "L" : "M"}${d.x},${d.y}`).join(" ");
  const xTicks = xTickIndices(
    times,
    dots.map((d) => d.x),
  );
  const hasBand = normal !== undefined && (normal.low !== undefined || normal.high !== undefined);
  const bandTop = y(Math.min(normal?.high ?? yMax, yMax));
  const bandBottom = y(Math.max(normal?.low ?? yMin, yMin));
  const last = dots[dots.length - 1] ?? { x: 0, y: 0, value: 0 };
  const current = active === null ? null : (dots[active] ?? null);
  // Keep the label inside the plot and off any marker within reach of it.
  const labelY = Math.min(Math.max(last.y, M.top + 8), H - M.bottom - 8);

  function nearest(clientX: number, svg: SVGSVGElement) {
    const box = svg.getBoundingClientRect();
    const px = ((clientX - box.left) / box.width) * W;
    let best = 0;
    dots.forEach((d, i) => {
      if (Math.abs(d.x - px) < Math.abs((dots[best]?.x ?? 0) - px)) best = i;
    });
    setActive(best);
  }

  const anchorFor = (i: number) =>
    points.length === 1 ? "middle" : i === 0 ? "start" : i === points.length - 1 ? "end" : "middle";

  return (
    <figure className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full touch-none"
        role="group"
        aria-labelledby={titleId}
        onPointerMove={(e) => nearest(e.clientX, e.currentTarget)}
        onPointerLeave={() => setActive(null)}
      >
        <title id={titleId}>{`${label} over time, ${points.length} readings`}</title>
        {hasBand && (
          <g aria-hidden="true">
            <rect
              x={M.left}
              y={bandTop}
              width={W - M.left - M.right}
              height={Math.max(0, bandBottom - bandTop)}
              fill="var(--chart-band)"
            />
            <text x={M.left + 6} y={bandTop + 14} className="fill-[var(--chart-axis)] text-[11px]">
              normal range
            </text>
          </g>
        )}
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
                {t}
              </text>
            </g>
          ))}
          {xTicks.map((i) => {
            const d = dots[i];
            if (!d) return null;
            return (
              <text
                key={i}
                x={d.x}
                y={H - M.bottom + 20}
                textAnchor={anchorFor(i)}
                className="fill-[var(--chart-axis)] text-[11px]"
              >
                {new Date(d.at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </text>
            );
          })}
          {current && (
            <line
              x1={current.x}
              x2={current.x}
              y1={M.top}
              y2={H - M.bottom}
              stroke="var(--chart-axis)"
              strokeWidth={1}
            />
          )}
          <path
            d={path}
            fill="none"
            stroke="var(--chart-series)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </g>
        {dots.map((d, i) => (
          <g
            key={i}
            tabIndex={0}
            role="img"
            aria-label={`${formatDateTime(d.at)}: ${d.value} ${unit}, ${FLAG_META[d.flag].label}`}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
            className="outline-none [&:focus-visible>circle:first-child]:stroke-[var(--chart-axis)]"
          >
            <circle cx={d.x} cy={d.y} r={12} fill="transparent" />
            <Marker flag={d.flag} x={d.x} y={d.y} r={active === i ? 6 : 4.5} />
          </g>
        ))}
        <text
          x={last.x + 14}
          y={labelY}
          dy="0.32em"
          stroke="var(--chart-surface)"
          strokeWidth={4}
          paintOrder="stroke"
          className="fill-[var(--foreground)] text-[12px] font-semibold tabular-nums"
          aria-hidden="true"
        >
          {last.value} {unit}
        </text>
      </svg>
      {current && (
        <div
          role="status"
          className="border-line bg-surface shadow-lift pointer-events-none absolute top-2 w-44 rounded-xl border px-3 py-2 text-sm"
          style={{
            left: `clamp(0px, calc(${(current.x / W) * 100}% - 88px), calc(100% - 176px))`,
          }}
        >
          <div className="font-semibold tabular-nums">
            {current.value} {unit}
          </div>
          <div className="text-ink-2">{formatDateTime(current.at)}</div>
          <div className="mt-1">
            <span aria-hidden="true">{FLAG_META[current.flag].icon}</span>{" "}
            {FLAG_META[current.flag].label}
          </div>
        </div>
      )}
      <figcaption className="text-ink-2 mt-2 flex flex-wrap gap-4 text-xs">
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" aria-hidden="true">
            <circle cx="6" cy="6" r="4" fill="var(--chart-series)" />
          </svg>
          Normal
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" aria-hidden="true">
            <polygon points="6,1 11,10 1,10" fill="var(--chart-warning)" />
          </svg>
          Warning
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" aria-hidden="true">
            <polygon points="6,0 12,6 6,12 0,6" fill="var(--chart-critical)" />
          </svg>
          Critical
        </span>
      </figcaption>
    </figure>
  );
}
