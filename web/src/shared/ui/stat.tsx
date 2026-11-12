import type { ReactNode } from "react";

import { Card } from "./card";

/** A headline number. `attention` tints the icon tile amber; the number itself never changes colour. */
export function StatCard({
  icon,
  label,
  value,
  unit,
  hint,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  unit?: string;
  hint: string;
  tone?: "neutral" | "attention";
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <span className="text-ink-2 text-sm font-medium">{label}</span>
        <span
          className={`flex size-8 items-center justify-center rounded-lg ${
            tone === "attention"
              ? "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
              : "bg-brand-soft text-brand-text"
          }`}
        >
          {icon}
        </span>
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-ink text-[2rem] leading-none font-semibold tracking-[-0.035em] tabular-nums">
          {value}
        </span>
        {unit && <span className="text-ink-3 text-sm font-medium">{unit}</span>}
      </div>
      <div className="text-ink-3 mt-2 text-xs">{hint}</div>
    </Card>
  );
}
