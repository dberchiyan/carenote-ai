import type { Extraction } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardHeader } from "@/shared/ui/card";
import { Input, Select } from "@/shared/ui/field";
import { PillIcon, PlusIcon, XIcon } from "@/shared/ui/icons";

import type { DraftEditor } from "./use-draft-editor";

const ROUTES = ["oral", "iv", "subcutaneous", "inhaled", "intramuscular"];

export function MedicationsCard({
  payload,
  editor,
  editable,
}: {
  payload: Extraction;
  editor: DraftEditor;
  editable: boolean;
}) {
  return (
    <Card className="p-6">
      <CardHeader icon={<PillIcon size={17} />} title="Medications given" />
      {payload.medications.length === 0 && (
        <p className="text-ink-3 mb-3 text-sm">None recorded.</p>
      )}
      <ul className="flex flex-col gap-2">
        {payload.medications.map((m, i) => (
          <li
            key={i}
            className="bg-surface-2 ring-line grid grid-cols-2 gap-2 rounded-xl p-2 ring-1 ring-inset sm:grid-cols-[minmax(0,1fr)_7rem_9rem_auto]"
            onMouseEnter={() => editor.focusText(m.source_text)}
            onMouseLeave={() => editor.focusText(null)}
          >
            <Input
              id={`input-med-${i}`}
              aria-label={`Medication ${i + 1} name`}
              className="font-medium"
              value={m.name}
              disabled={!editable}
              onFocus={() => editor.focusText(m.source_text)}
              onChange={(e) => editor.medications.update(i, { name: e.target.value })}
            />
            <Input
              aria-label={`Medication ${i + 1} dose`}
              placeholder="Dose"
              value={m.dose ?? ""}
              disabled={!editable}
              onChange={(e) => editor.medications.update(i, { dose: e.target.value || null })}
            />
            <Select
              aria-label={`Medication ${i + 1} route`}
              value={m.route ?? ""}
              disabled={!editable}
              onChange={(e) => editor.medications.update(i, { route: e.target.value || null })}
            >
              <option value="">Route…</option>
              {ROUTES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
            {editable && (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove medication ${m.name}`}
                onClick={() => editor.medications.remove(i)}
              >
                <XIcon size={16} />
              </Button>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={editor.medications.add}>
          <PlusIcon size={15} />
          Add medication
        </Button>
      )}
    </Card>
  );
}
