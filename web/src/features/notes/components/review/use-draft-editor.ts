"use client";

import { useState } from "react";

import type { Extraction, Medication, Note, Vital } from "@/shared/api/types";
import { UCUM } from "@/shared/lib/vitals";

/**
 * The nurse's working copy of the draft. Every edit marks it dirty; `invalid` blocks confirm
 * while a vital has no value. `activeText` links a focused field to its words in the transcript.
 */
export function useDraftEditor(note: Note) {
  const draft = note.draft;
  const [payload, setPayload] = useState<Extraction | null>(
    draft ? structuredClone(draft.payload) : null,
  );
  const [patientId, setPatientId] = useState<string | null>(note.patient_id);
  const [dirty, setDirty] = useState(false);
  const [activeText, setActiveText] = useState<string | null>(null);

  const update = (next: Extraction) => {
    setPayload(next);
    setDirty(true);
  };
  const patch = (changes: Partial<Extraction>) => payload && update({ ...payload, ...changes });

  return {
    payload,
    patientId,
    dirty,
    setDirty,
    activeText,
    /** Highlight the transcript words a field came from (null clears). */
    focusText: (text: string | null) => setActiveText(text ? text.toLowerCase() : null),
    invalid: payload?.vitals.some((v) => Number.isNaN(v.value)) ?? false,
    selectPatient: (id: string) => {
      setPatientId(id);
      if (id !== note.patient_id) setDirty(true);
    },
    vitals: {
      update: (i: number, changes: Partial<Vital>) =>
        patch({ vitals: payload?.vitals.map((v, j) => (j === i ? { ...v, ...changes } : v)) }),
      setKind: (i: number, kind: Vital["kind"]) =>
        patch({
          vitals: payload?.vitals.map((v, j) => (j === i ? { ...v, kind, unit: UCUM[kind] } : v)),
        }),
      remove: (i: number) => patch({ vitals: payload?.vitals.filter((_, j) => j !== i) }),
      add: () =>
        patch({
          vitals: [
            ...(payload?.vitals ?? []),
            { kind: "heart_rate", value: NaN, unit: "/min", source_text: "" },
          ],
        }),
    },
    symptoms: {
      add: (symptom: string) => {
        const value = symptom.trim().toLowerCase();
        if (value && payload && !payload.symptoms.includes(value)) {
          patch({ symptoms: [...payload.symptoms, value] });
        }
      },
      remove: (i: number) => patch({ symptoms: payload?.symptoms.filter((_, j) => j !== i) }),
    },
    medications: {
      update: (i: number, changes: Partial<Medication>) =>
        patch({
          medications: payload?.medications.map((m, j) => (j === i ? { ...m, ...changes } : m)),
        }),
      remove: (i: number) => patch({ medications: payload?.medications.filter((_, j) => j !== i) }),
      add: () =>
        patch({
          medications: [
            ...(payload?.medications ?? []),
            { name: "", dose: null, route: null, source_text: "" },
          ],
        }),
    },
  };
}

export type DraftEditor = ReturnType<typeof useDraftEditor>;
