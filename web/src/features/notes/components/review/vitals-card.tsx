import type { Draft, Extraction, VitalKind } from "@/shared/api/types";
import { VITAL_KINDS, VITAL_LABELS } from "@/shared/lib/vitals";
import { Button } from "@/shared/ui/button";
import { Card, CardHeader } from "@/shared/ui/card";
import { Input, Select } from "@/shared/ui/field";
import { FlagBadge } from "@/shared/ui/flag-badge";
import { AlertIcon, HeartPulseIcon, PlusIcon, UndoIcon, XIcon } from "@/shared/ui/icons";

import type { DraftEditor } from "./use-draft-editor";

const VITAL_OPTIONS = VITAL_KINDS.map((k) => ({
  value: k,
  label: VITAL_LABELS[k].label,
  hint: VITAL_LABELS[k].unit,
}));

export function VitalsCard({
  draft,
  payload,
  editor,
  editable,
}: {
  draft: Draft;
  payload: Extraction;
  editor: DraftEditor;
  editable: boolean;
}) {
  const savedValue = (kind: VitalKind) => draft.payload.vitals.find((s) => s.kind === kind)?.value;
  return (
    <Card className="p-6">
      <CardHeader
        icon={<HeartPulseIcon size={17} />}
        title="Vital signs"
        description="Units normalised to UCUM. Flags from the ward's alert rules."
      />
      {payload.vitals.length === 0 && (
        <p className="text-ink-3 mb-3 text-sm">No vital signs recognised.</p>
      )}
      <ul className="flex flex-col gap-2">
        {payload.vitals.map((v, i) => {
          const changed = savedValue(v.kind) !== v.value;
          const flag = draft.flags[v.kind];
          // Hints come from the AI's version; a field the nurse has changed no longer needs one.
          const hints = changed ? [] : draft.hints.filter((h) => h.kind === v.kind);
          return (
            <li
              key={i}
              className="bg-surface-2 ring-line grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-xl p-2 ring-1 ring-inset sm:grid-cols-[12rem_9rem_minmax(0,1fr)_auto]"
            >
              <span className="col-start-1 row-start-1 min-w-0 sm:col-auto sm:row-auto">
                <Select<VitalKind>
                  aria-label={`Vital ${i + 1} kind`}
                  title="Vital sign"
                  value={v.kind}
                  disabled={!editable}
                  onChange={(k) => editor.vitals.setKind(i, k)}
                  options={VITAL_OPTIONS}
                />
              </span>
              <Input
                id={`input-vital-${i}`}
                aria-label={`${VITAL_LABELS[v.kind].label} value`}
                type="number"
                step="any"
                inputMode="decimal"
                suffix={VITAL_LABELS[v.kind].unit}
                className="col-span-full text-right font-semibold tabular-nums sm:col-span-1"
                value={Number.isNaN(v.value) ? "" : v.value}
                disabled={!editable}
                onFocus={() => editor.focusText(v.source_text)}
                onBlur={() => editor.focusText(null)}
                onMouseEnter={() => editor.focusText(v.source_text)}
                onMouseLeave={() => editor.focusText(null)}
                onChange={(e) => editor.vitals.update(i, { value: e.target.valueAsNumber })}
                aria-describedby={hints.length > 0 ? `hint-vital-${i}` : undefined}
              />
              <span className="col-span-full px-1 sm:col-span-1 sm:col-start-3">
                {changed || !flag ? (
                  <span className="text-ink-3 text-xs">Re-checked on save</span>
                ) : (
                  <FlagBadge flag={flag} />
                )}
              </span>
              {editable && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${VITAL_LABELS[v.kind].label}`}
                  onClick={() => editor.vitals.remove(i)}
                  className="col-start-2 row-start-1 justify-self-end sm:col-auto sm:row-auto"
                >
                  <XIcon size={16} />
                </Button>
              )}
              {hints.length > 0 && (
                <ul id={`hint-vital-${i}`} className="col-span-full flex flex-wrap gap-1.5 px-1">
                  {hints.map((h) => (
                    <li
                      key={h.reason}
                      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                        h.reason === "not_in_transcript"
                          ? "bg-red-50 text-red-800 ring-red-200 dark:bg-red-950/50 dark:text-red-200 dark:ring-red-800/60"
                          : "bg-amber-50 text-amber-900 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-100 dark:ring-amber-700/50"
                      }`}
                    >
                      {h.reason === "not_in_transcript" ? (
                        <AlertIcon size={13} />
                      ) : (
                        <UndoIcon size={13} />
                      )}
                      {h.message}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
      {editable && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={editor.vitals.add}>
          <PlusIcon size={15} />
          Add vital sign
        </Button>
      )}
    </Card>
  );
}
