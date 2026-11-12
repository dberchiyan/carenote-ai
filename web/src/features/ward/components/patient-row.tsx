import Link from "next/link";

import type { LatestVital, WardPatient } from "@/shared/api/types";
import { ageFrom, initials } from "@/shared/lib/format";
import { isFlag, isVitalKind, VITAL_LABELS, worstFlag } from "@/shared/lib/vitals";
import { FlagBadge } from "@/shared/ui/flag-badge";
import { Pill } from "@/shared/ui/states";

/** The latest value of each vital as compact chips; BP is shown as one systolic/diastolic pair. */
export function LatestVitals({ vitals }: { vitals: LatestVital[] }) {
  if (vitals.length === 0) return <span className="text-ink-3">No readings yet</span>;
  const byKind = Object.fromEntries(vitals.map((v) => [v.kind, v]));
  const sys = byKind.systolic_bp;
  const dia = byKind.diastolic_bp;
  const items: { label: string; value: string; flag: string }[] = [];
  if (sys && dia) {
    items.push({
      label: "BP",
      value: `${sys.value}/${dia.value}`,
      flag: worstFlag([sys.flag, dia.flag].filter(isFlag)),
    });
  }
  for (const v of vitals) {
    if (v.kind === "systolic_bp" || v.kind === "diastolic_bp" || !isVitalKind(v.kind)) continue;
    items.push({ label: VITAL_LABELS[v.kind].short, value: String(v.value), flag: v.flag });
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => {
        const flagged = isFlag(item.flag) && item.flag !== "normal";
        return (
          <li
            key={item.label}
            className={`flex items-center gap-1.5 rounded-lg px-2 py-1 whitespace-nowrap ring-1 ring-inset ${
              flagged ? "bg-surface ring-line-strong" : "bg-surface-2 ring-line"
            }`}
          >
            <span className="text-ink-3 text-[11px] font-medium">{item.label}</span>
            <span className="text-ink font-semibold tabular-nums">{item.value}</span>
            {flagged && isFlag(item.flag) && <FlagBadge flag={item.flag} compact />}
          </li>
        );
      })}
    </ul>
  );
}

export function PatientRow({ p }: { p: WardPatient }) {
  const flags = p.latest_vitals.map((v) => v.flag).filter(isFlag);
  const worst = worstFlag(flags);
  return (
    <tr className="group border-line hover:bg-surface-2 border-b transition-colors last:border-0">
      <td className="py-3.5 pr-3 pl-5">
        <span className="bg-surface-3 text-ink-2 inline-flex min-w-12 justify-center rounded-md px-2 py-1 font-mono text-xs font-medium">
          {p.room}
        </span>
      </td>
      <td className="px-3 py-3.5">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="bg-surface-3 text-ink-2 hidden size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold sm:flex"
          >
            {initials(`${p.given_name} ${p.family_name}`)}
          </span>
          <div className="min-w-0">
            <Link
              href={`/patients/${p.id}`}
              className="text-ink decoration-brand/40 group-hover:text-brand-text focus-visible:outline-brand-ring font-semibold whitespace-nowrap underline-offset-4 hover:underline focus-visible:outline-2"
            >
              {p.family_name}, {p.given_name}
            </Link>
            <div className="text-ink-3 text-xs whitespace-nowrap tabular-nums">
              {ageFrom(p.birth_date)} y · {p.sex === "female" ? "F" : "M"} · {p.mrn}
            </div>
          </div>
        </div>
      </td>
      <td className="px-3 py-3.5">
        {flags.length > 0 ? <FlagBadge flag={worst} /> : <span className="text-ink-3">—</span>}
      </td>
      <td className="px-3 py-3.5">
        <LatestVitals vitals={p.latest_vitals} />
      </td>
      <td className="py-3.5 pr-5 pl-3 text-right">
        {p.open_drafts > 0 && (
          <Pill tone="info">
            {p.open_drafts} draft{p.open_drafts > 1 ? "s" : ""}
          </Pill>
        )}
      </td>
    </tr>
  );
}

/** The phone version of a table row: everything the row shows, stacked, one tap target. */
export function PatientCard({ p }: { p: WardPatient }) {
  const flags = p.latest_vitals.map((v) => v.flag).filter(isFlag);
  const worst = worstFlag(flags);
  return (
    <li>
      <Link
        href={`/patients/${p.id}`}
        className="card focus-visible:outline-brand-ring active:bg-surface-2 block p-3.5 focus-visible:outline-2"
      >
        <div className="flex items-center gap-3">
          <span className="bg-surface-3 text-ink-2 inline-flex min-w-12 justify-center rounded-md px-2 py-1 font-mono text-xs font-medium">
            {p.room}
          </span>
          <span className="min-w-0 flex-1">
            <span className="text-ink block truncate font-semibold">
              {p.family_name}, {p.given_name}
            </span>
            <span className="text-ink-3 block text-xs tabular-nums">
              {ageFrom(p.birth_date)} y · {p.sex === "female" ? "F" : "M"} · {p.mrn}
            </span>
          </span>
          {flags.length > 0 && <FlagBadge flag={worst} />}
        </div>
        {(p.latest_vitals.length > 0 || p.open_drafts > 0) && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <LatestVitals vitals={p.latest_vitals} />
            {p.open_drafts > 0 && (
              <Pill tone="info" className="ml-auto">
                {p.open_drafts} draft{p.open_drafts > 1 ? "s" : ""}
              </Pill>
            )}
          </div>
        )}
      </Link>
    </li>
  );
}
