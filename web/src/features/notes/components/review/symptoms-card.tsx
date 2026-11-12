import { useState } from "react";

import type { Extraction } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";
import { Card, CardHeader } from "@/shared/ui/card";
import { Input } from "@/shared/ui/field";
import { ActivityIcon, XIcon } from "@/shared/ui/icons";

import type { DraftEditor } from "./use-draft-editor";

export function SymptomsCard({
  payload,
  editor,
  editable,
}: {
  payload: Extraction;
  editor: DraftEditor;
  editable: boolean;
}) {
  const [newSymptom, setNewSymptom] = useState("");
  return (
    <Card className="p-6">
      <CardHeader icon={<ActivityIcon size={17} />} title="Symptoms" />
      <ul className="flex flex-wrap gap-2">
        {payload.symptoms.length === 0 && <li className="text-ink-3 text-sm">None recorded.</li>}
        {payload.symptoms.map((s, i) => (
          <li
            key={s}
            className="bg-surface-3 text-ink ring-line inline-flex items-center gap-1 rounded-full py-1 pr-1 pl-3 text-sm font-medium ring-1 ring-inset"
          >
            {s}
            {editable && (
              <button
                type="button"
                aria-label={`Remove symptom ${s}`}
                onClick={() => editor.symptoms.remove(i)}
                className="text-ink-3 hover:bg-surface hover:text-ink focus-visible:outline-brand-ring flex size-6 items-center justify-center rounded-full focus-visible:outline-2"
              >
                <XIcon size={13} />
              </button>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            editor.symptoms.add(newSymptom);
            setNewSymptom("");
          }}
        >
          <Input
            aria-label="Add symptom"
            placeholder="Add symptom"
            value={newSymptom}
            onChange={(e) => setNewSymptom(e.target.value)}
          />
          <Button type="submit" variant="secondary" size="sm">
            Add
          </Button>
        </form>
      )}
    </Card>
  );
}
