import type { Note, WardPatient } from "@/shared/api/types";
import { Card, CardHeader } from "@/shared/ui/card";
import { Select } from "@/shared/ui/field";
import { AlertIcon, UsersIcon } from "@/shared/ui/icons";

export function PatientCard({
  note,
  patientId,
  wardPatients,
  editable,
  onSelect,
}: {
  note: Note;
  patientId: string | null;
  wardPatients: WardPatient[] | undefined;
  editable: boolean;
  onSelect: (id: string) => void;
}) {
  const selected =
    note.candidates.find((c) => c.patient_id === patientId) ??
    wardPatients?.find((p) => p.id === patientId);
  const matched = note.match_status === "matched" && note.patient_id === patientId && selected;
  return (
    <Card className="p-6">
      <CardHeader
        icon={<UsersIcon size={17} />}
        title="Patient"
        description={
          matched
            ? `Matched automatically from the transcript${
                "score" in selected ? ` (${Math.round(selected.score)}% name match)` : ""
              }.`
            : undefined
        }
      />
      {!patientId && (
        <p className="bg-warn-soft text-warn-fg mb-3 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium">
          <AlertIcon size={15} />
          {note.match_status === "ambiguous"
            ? "Several patients could match. Choose the right one."
            : note.candidates.length > 0
              ? "Only a first name was heard. Confirm who this is."
              : "No patient recognised. Choose the patient."}
        </p>
      )}
      <fieldset disabled={!editable} className="flex flex-col gap-2">
        <legend className="sr-only">Select patient</legend>
        {note.candidates.map((c) => {
          const checked = patientId === c.patient_id;
          return (
            <label
              key={c.patient_id}
              className={`has-[:focus-visible]:outline-brand-ring flex cursor-pointer items-center gap-3 rounded-xl border p-3.5 transition-colors has-[:focus-visible]:outline-2 ${
                checked
                  ? "border-brand/50 bg-brand-soft shadow-[0_0_0_3px_color-mix(in_oklab,var(--brand-ring)_12%,transparent)]"
                  : "border-line hover:border-line-strong hover:bg-surface-2"
              }`}
            >
              <input
                type="radio"
                name="patient"
                checked={checked}
                onChange={() => onSelect(c.patient_id)}
                className="size-4 accent-teal-700"
              />
              <span
                aria-hidden="true"
                className="bg-surface text-ink-2 ring-line flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1"
              >
                {c.given_name[0]}
                {c.family_name[0]}
              </span>
              <span className="min-w-0 flex-1">
                <span className="text-ink block font-semibold">
                  {c.family_name}, {c.given_name}
                </span>
                <span className="text-ink-3 block text-xs"> Room {c.room}</span>
              </span>
              <span className="flex flex-col items-end gap-1">
                <span className="text-ink-2 text-xs font-semibold tabular-nums">
                  {Math.round(c.score)}% match
                </span>
                <span aria-hidden="true" className="bg-line h-1 w-16 overflow-hidden rounded-full">
                  <span
                    className="bg-brand block h-full rounded-full"
                    style={{ width: `${Math.round(c.score)}%` }}
                  />
                </span>
              </span>
            </label>
          );
        })}
        <label className="mt-2 flex flex-col gap-1.5 text-sm">
          <span className="text-ink-2">
            {note.candidates.length ? "Or choose another patient on the ward" : "Patient"}
          </span>
          <Select
            title="Patient"
            placeholder="Choose a patient…"
            searchPlaceholder="Name, room or MRN"
            searchable
            disabled={!editable}
            value={patientId}
            onChange={onSelect}
            options={(wardPatients ?? []).map((p) => ({
              value: p.id,
              label: `${p.family_name}, ${p.given_name}`,
              description: `Room ${p.room} · ${p.mrn}`,
              keywords: `${p.given_name} ${p.family_name} ${p.mrn}`,
            }))}
          />
        </label>
      </fieldset>
    </Card>
  );
}
