"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { patientKeys } from "@/features/patients/keys";
import { wardKeys } from "@/features/ward/keys";
import type { Extraction, Note, NoteStatus } from "@/shared/api/types";

import { notesApi, type Upload } from "./api";
import { noteKeys } from "./keys";

const PROCESSING: NoteStatus[] = ["uploaded", "transcribed"];

/** Still being worked on. A failed or stalled note is not: it waits for a retry. */
export function isProcessing(note: Note): boolean {
  return PROCESSING.includes(note.status) && !note.error_step && !note.stalled;
}

export function useNote(id: string) {
  return useQuery({
    queryKey: noteKeys.detail(id),
    queryFn: () => notesApi.get(id),
    refetchInterval: (query) => (query.state.data && isProcessing(query.state.data) ? 800 : false),
    // Processing takes seconds and always ends (ready or error_step). Keep polling even when the
    // browser reports the page as hidden (automation, embedded views), or it hangs on "Processing".
    refetchIntervalInBackground: true,
  });
}

export function useNotes() {
  return useQuery({ queryKey: noteKeys.list(), queryFn: notesApi.list });
}

/** Every note mutation lands the fresh note in the cache and refreshes what it may have changed. */
function useNoteMutation<TVars>(fn: (vars: TVars) => Promise<Note>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (note) => {
      queryClient.setQueryData(noteKeys.detail(note.id), note);
      void queryClient.invalidateQueries({ queryKey: noteKeys.list() });
      void queryClient.invalidateQueries({ queryKey: wardKeys.all });
      if (note.status === "confirmed" && note.patient_id) {
        // Confirming writes observations: the patient's record and the ward's latest values.
        void queryClient.invalidateQueries({ queryKey: patientKeys.detail(note.patient_id) });
        void queryClient.invalidateQueries({ queryKey: patientKeys.observations(note.patient_id) });
      }
    },
  });
}

export function useCreateTextNote() {
  return useNoteMutation(notesApi.createText);
}

export function useUploadNote() {
  return useNoteMutation((upload: Upload) => notesApi.upload(upload));
}

export function useUpdateDraft(id: string) {
  return useNoteMutation((vars: { payload: Extraction; patientId: string | null }) =>
    notesApi.updateDraft(id, vars.payload, vars.patientId),
  );
}

export function useConfirm(id: string) {
  return useNoteMutation((patientId: string | null) => notesApi.confirm(id, patientId));
}

export function useReject(id: string) {
  return useNoteMutation((reason: string | null) => notesApi.reject(id, reason));
}

export function useRetry(id: string) {
  return useNoteMutation(() => notesApi.retry(id));
}

/** Server-side transcript of a recording that has not been sent yet (nothing is stored). */
export function useTranscribePreview() {
  return useMutation({ mutationFn: notesApi.transcribe });
}
