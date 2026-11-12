"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Recorder } from "@/features/notes/components/recorder";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/field";
import { LockIcon, MicIcon, ShieldIcon, SparkIcon, TypeIcon, UploadIcon } from "@/shared/ui/icons";
import { ErrorState, PageHeader } from "@/shared/ui/states";
import { useCreateTextNote, useUploadNote } from "@/features/notes/hooks";
import { usePageTitle } from "@/shared/lib/use-page-title";

type Mode = "record" | "upload" | "type";

const MODES: { key: Mode; label: string; icon: ReactNode }[] = [
  { key: "record", label: "Record", icon: <MicIcon size={16} /> },
  { key: "upload", label: "Upload file", icon: <UploadIcon size={16} /> },
  { key: "type", label: "Type", icon: <TypeIcon size={16} /> },
];

const EXAMPLES: { label: string; text: string }[] = [
  {
    label: "Full round",
    text: "Mrs. Anna Keller, blood pressure 150 over 90, pulse 88, temp thirty-seven point nine, complains of a headache, gave 500 mg paracetamol orally.",
  },
  {
    label: "Implausible value",
    text: "Mrs. Keller, BP 168/96, pulse 380, sats 91% on room air, denies chest pain.",
  },
  {
    label: "Self-correction",
    text: "Mr. John Smith, pulse 72, BP 140 over 85, sorry, correction, 145 over 85, temperature 36.8.",
  },
];

const STEPS: { icon: ReactNode; title: string; text: string }[] = [
  {
    icon: <MicIcon size={15} />,
    title: "Say it naturally",
    text: "Patient's name, values, symptoms and medications — in any order.",
  },
  {
    icon: <LockIcon size={15} />,
    title: "Private before AI",
    text: "The patient is matched on your ward list; names are replaced before extraction.",
  },
  {
    icon: <ShieldIcon size={15} />,
    title: "You confirm",
    text: "Every value is checked by you. Nothing is saved to the record before that.",
  },
];

export function NewNotePage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("record");
  usePageTitle("Record a note");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const upload = useUploadNote();
  const typed = useCreateTextNote();
  const busy = upload.isPending || typed.isPending;
  const error = upload.error ?? typed.error;
  const goToNote = { onSuccess: (note: { id: string }) => router.push(`/notes/${note.id}`) };

  return (
    <>
      <PageHeader
        eyebrow="New note"
        title="Record a note"
        subtitle="Say the patient's name, the values and anything else. You will review the draft before anything is saved."
      />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="p-2">
          <div
            role="tablist"
            aria-label="Input method"
            className="bg-surface-3 flex gap-1 rounded-xl p-1"
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              const i = MODES.findIndex((m) => m.key === mode);
              const next =
                MODES[(i + (e.key === "ArrowRight" ? 1 : MODES.length - 1)) % MODES.length];
              if (!next) return;
              setMode(next.key);
              document.getElementById(`tab-${next.key}`)?.focus();
            }}
          >
            {MODES.map((m) => (
              <button
                key={m.key}
                id={`tab-${m.key}`}
                role="tab"
                type="button"
                aria-selected={mode === m.key}
                aria-controls="input-panel"
                tabIndex={mode === m.key ? 0 : -1}
                onClick={() => setMode(m.key)}
                className={`focus-visible:outline-brand-ring flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg px-2 text-sm font-medium whitespace-nowrap transition-[background-color,color,box-shadow] focus-visible:outline-2 sm:px-3 ${
                  mode === m.key
                    ? "bg-surface text-ink shadow-[0_1px_2px_rgb(15_23_42/0.08),0_0_0_1px_var(--line)]"
                    : "text-ink-2 hover:text-ink"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`hidden sm:inline ${mode === m.key ? "text-brand-text" : ""}`}
                >
                  {m.icon}
                </span>
                {m.label}
              </button>
            ))}
          </div>
          <div
            id="input-panel"
            role="tabpanel"
            aria-labelledby={`tab-${mode}`}
            className="p-6 sm:p-8"
          >
            {mode === "record" && (
              <Recorder
                busy={busy}
                onSubmit={(recording) =>
                  upload.mutate(
                    { file: recording.blob, transcript: recording.transcript },
                    goToNote,
                  )
                }
              />
            )}

            {mode === "upload" && (
              <form
                className="flex flex-col gap-5"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (file) upload.mutate({ file }, goToNote);
                }}
              >
                <label className="text-ink flex flex-col gap-2 text-sm font-medium">
                  Audio file (WebM, WAV, MP3 or M4A, up to 2 minutes)
                  <span className="border-line-strong bg-surface-2 has-[:focus-visible]:border-brand-ring hover:border-brand/50 relative flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-6 py-10 text-center transition-colors">
                    <span className="bg-brand-soft text-brand-text flex size-11 items-center justify-center rounded-xl">
                      <UploadIcon />
                    </span>
                    <span className="text-ink text-sm font-semibold">
                      {file ? file.name : "Choose an audio file"}
                    </span>
                    <span className="text-ink-3 text-xs font-normal">
                      {file
                        ? `${(file.size / 1024).toFixed(0)} KB · ready to upload`
                        : "or drop it here"}
                    </span>
                    <input
                      type="file"
                      name="audio"
                      accept="audio/webm,audio/wav,audio/x-wav,audio/mpeg,audio/mp4,audio/x-m4a,.webm,.wav,.mp3,.m4a"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      className="absolute inset-0 cursor-pointer opacity-0"
                    />
                  </span>
                </label>
                <Button type="submit" disabled={!file || busy}>
                  {busy ? "Uploading…" : "Upload and process"}
                </Button>
              </form>
            )}

            {mode === "type" && (
              <form
                className="flex flex-col gap-5"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (text.trim().length >= 3) typed.mutate(text, goToNote);
                }}
              >
                <label className="text-ink flex flex-col gap-2 text-sm font-medium">
                  Note text
                  <Textarea
                    name="text"
                    rows={6}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Mrs. Anna Keller, blood pressure 150 over 90, pulse 88, complains of a headache, gave 500 mg paracetamol."
                    className="p-4 text-[15px] font-normal"
                  />
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="eyebrow mr-1">Try an example</span>
                  {EXAMPLES.map((ex) => (
                    <button
                      key={ex.label}
                      type="button"
                      onClick={() => setText(ex.text)}
                      className="bg-surface text-ink-2 ring-line-strong hover:bg-brand-soft hover:text-brand-text hover:ring-brand/30 focus-visible:outline-brand-ring rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset focus-visible:outline-2"
                    >
                      {ex.label}
                    </button>
                  ))}
                </div>
                <Button type="submit" disabled={text.trim().length < 3 || busy}>
                  <SparkIcon size={16} />
                  {busy ? "Processing…" : "Create draft"}
                </Button>
              </form>
            )}

            {error && (
              <div className="mt-5">
                <ErrorState error={error} />
              </div>
            )}
          </div>
        </Card>

        <aside aria-labelledby="how-heading" className="flex flex-col gap-4">
          <Card className="p-6">
            <h2 id="how-heading" className="eyebrow mb-5">
              How it works
            </h2>
            <ol className="relative flex flex-col gap-6">
              <span
                aria-hidden="true"
                className="from-line-strong via-line absolute top-3 bottom-3 left-[15px] w-px bg-gradient-to-b to-transparent"
              />
              {STEPS.map((s) => (
                <li key={s.title} className="relative flex gap-4">
                  <span className="bg-surface text-brand-text ring-line-strong relative flex size-8 shrink-0 items-center justify-center rounded-full ring-1">
                    {s.icon}
                  </span>
                  <span>
                    <span className="text-ink block text-sm font-semibold">{s.title}</span>
                    <span className="text-ink-3 mt-0.5 block text-[13px] leading-snug">
                      {s.text}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </Card>
          <p className="text-ink-3 px-1 text-xs leading-relaxed">
            Demo with synthetic patients only. Never dictate real patient information.
          </p>
        </aside>
      </div>
    </>
  );
}
