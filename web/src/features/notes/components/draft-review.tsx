"use client";

import { useMe } from "@/features/auth/hooks";
import { useConfirm, useReject, useUpdateDraft } from "@/features/notes/hooks";
import { usePatients } from "@/features/ward/hooks";
import type { Note } from "@/shared/api/types";
import { VITAL_LABELS } from "@/shared/lib/vitals";
import { Card, CardHeader } from "@/shared/ui/card";
import { AlertIcon, SparkIcon } from "@/shared/ui/icons";
import { ErrorState } from "@/shared/ui/states";

import { MedicationsCard } from "./review/medications-card";
import { DraftMeta, OutcomeBanner } from "./review/outcome";
import { PatientCard } from "./review/patient-card";
import { ReviewActions } from "./review/review-actions";
import { SymptomsCard } from "./review/symptoms-card";
import { TranscriptCard } from "./review/transcript-card";
import { useDraftEditor } from "./review/use-draft-editor";
import { VitalsCard } from "./review/vitals-card";

/** The review screen: the transcript on the left, the editable draft and its outcome on the right. */
export function DraftReview({ note }: { note: Note }) {
  const draft = note.draft;
  const me = useMe();
  const editor = useDraftEditor(note);
  const save = useUpdateDraft(note.id);
  const confirm = useConfirm(note.id);
  const reject = useReject(note.id);
  const wardPatients = usePatients();

  const { payload, patientId } = editor;
  if (!draft || !payload) return null;

  const editable = note.status === "in_review" && me.data?.role !== "auditor";
  const busy = save.isPending || confirm.isPending || reject.isPending;
  const error = save.error ?? confirm.error ?? reject.error;
  const attention = [
    ...payload.uncertain,
    ...draft.hints.map((h) => `${VITAL_LABELS[h.kind].label}: ${h.message}`),
  ];

  async function onConfirm() {
    if (!payload) return;
    if (editor.dirty) {
      try {
        await save.mutateAsync({ payload, patientId });
      } catch {
        return; // the save's error is shown; nothing is confirmed on top of a failed save
      }
      editor.setDirty(false);
    }
    confirm.mutate(patientId);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <TranscriptCard
        note={note}
        payload={payload}
        activeText={editor.activeText}
        onHover={editor.focusText}
      />

      <div className="flex min-w-0 flex-col gap-5">
        {attention.length > 0 && (
          <section
            aria-labelledby="uncertain-heading"
            className="shadow-card border-warn-line bg-warn-soft text-warn-fg flex gap-4 rounded-2xl border p-5"
          >
            <span className="bg-surface text-warn ring-warn-line flex size-9 shrink-0 items-center justify-center rounded-lg ring-1">
              <AlertIcon size={17} />
            </span>
            <div className="min-w-0">
              <h2 id="uncertain-heading" className="font-semibold">
                Needs your attention ({attention.length})
              </h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed">
                {attention.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <PatientCard
          note={note}
          patientId={patientId}
          wardPatients={wardPatients.data}
          editable={editable}
          onSelect={editor.selectPatient}
        />
        <VitalsCard draft={draft} payload={payload} editor={editor} editable={editable} />
        <div className="grid gap-5 xl:grid-cols-2">
          <SymptomsCard payload={payload} editor={editor} editable={editable} />
          <Card className="p-6">
            <CardHeader icon={<SparkIcon size={17} />} title="Summary" />
            <p className="text-ink-2 text-[15px] leading-relaxed">{payload.free_text_summary}</p>
          </Card>
        </div>
        <MedicationsCard payload={payload} editor={editor} editable={editable} />

        <DraftMeta draft={draft} />
        <OutcomeBanner note={note} />
        {error && <ErrorState error={error} />}

        {editable && (
          <ReviewActions
            busy={busy}
            dirty={editor.dirty}
            invalid={editor.invalid}
            patientSelected={!!patientId}
            saving={save.isPending}
            confirming={confirm.isPending}
            onSave={() =>
              save.mutate({ payload, patientId }, { onSuccess: () => editor.setDirty(false) })
            }
            onConfirm={() => void onConfirm()}
            onReject={(reason) => reject.mutate(reason)}
          />
        )}
      </div>
    </div>
  );
}
