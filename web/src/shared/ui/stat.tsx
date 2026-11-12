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
    <Card className="p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <span className="text-ink-2 text-sm font-medium">{label}</span>
        <span
          className={`flex size-8 items-center justify-center rounded-lg ${
            tone === "attention" ? "bg-warn-soft text-warn" : "bg-brand-soft text-brand-text"
          }`}
        >
          {icon}
        </span>
      </div>
      <div className="mt-2.5 flex items-baseline gap-1 sm:mt-3">
        <span className="text-ink text-[1.75rem] leading-none font-semibold tracking-[-0.035em] tabular-nums sm:text-[2rem]">
          {value}
        </span>
        {unit && <span className="text-ink-3 text-sm font-medium">{unit}</span>}
      </div>
      <div className="text-ink-3 mt-2 text-xs">{hint}</div>
    </Card>
  );
}
