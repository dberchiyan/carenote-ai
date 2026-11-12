import { api } from "@/shared/api/client";
import { throwIfNotOk, unwrap } from "@/shared/api/errors";
import type { Extraction, Note } from "@/shared/api/types";

export type Upload = { file: Blob; transcript?: string | null };

export type TranscriptPreview = { text: string; model: string; latency_ms: number };

export const notesApi = {
  list: async () => unwrap(await api.GET("/notes")),
  /** Transcribe a recording before it is sent, so the nurse can read and fix the text. */
  transcribe: async (file: Blob): Promise<TranscriptPreview> => {
    const form = new FormData();
    const ext = file.type.includes("mp4") ? "m4a" : file.type.includes("wav") ? "wav" : "webm";
    form.append("audio", file, `recording.${ext}`);
    const response = await fetch(`${window.location.origin}/api/notes/transcribe`, {
      method: "POST",
      body: form,
    });
    await throwIfNotOk(response, "Transcription failed");
    return (await response.json()) as TranscriptPreview;
  },
  get: async (id: string) =>
    unwrap(await api.GET("/notes/{note_id}", { params: { path: { note_id: id } } })),
  createText: async (text: string) => unwrap(await api.POST("/notes/text", { body: { text } })),
  /** Multipart upload; openapi-fetch's JSON client does not serialise FormData, so use fetch. */
  upload: async ({ file, transcript }: Upload): Promise<Note> => {
    const form = new FormData();
    const ext = file.type.includes("mp4") ? "m4a" : file.type.includes("wav") ? "wav" : "webm";
    form.append("audio", file, file instanceof File ? file.name : `recording.${ext}`);
    if (transcript) form.append("transcript", transcript);
    const response = await fetch(`${window.location.origin}/api/notes`, {
      method: "POST",
      body: form,
    });
    await throwIfNotOk(response, "Upload failed");
    return (await response.json()) as Note;
  },
  updateDraft: async (id: string, payload: Extraction, patientId: string | null) =>
    unwrap(
      await api.PATCH("/notes/{note_id}/draft", {
        params: { path: { note_id: id } },
        body: { payload, patient_id: patientId },
      }),
    ),
  confirm: async (id: string, patientId: string | null) =>
    unwrap(
      await api.POST("/notes/{note_id}/confirm", {
        params: { path: { note_id: id } },
        body: { patient_id: patientId },
      }),
    ),
  reject: async (id: string, reason: string | null) =>
    unwrap(
      await api.POST("/notes/{note_id}/reject", {
        params: { path: { note_id: id } },
        body: { reason },
      }),
    ),
  retry: async (id: string) =>
    unwrap(await api.POST("/notes/{note_id}/retry", { params: { path: { note_id: id } } })),
};
