import { useMemo } from "react";

import { highlightSegments } from "@/features/notes/lib/highlight";
import type { Extraction, Note } from "@/shared/api/types";
import { Card } from "@/shared/ui/card";
import { SparkIcon } from "@/shared/ui/icons";
import { Pill } from "@/shared/ui/states";

export function TranscriptCard({
  note,
  payload,
  activeText,
  onHover,
}: {
  note: Note;
  payload: Extraction;
  activeText: string | null;
  onHover: (text: string | null) => void;
}) {
  const segments = useMemo(() => {
    if (!note.transcript) return [];
    return highlightSegments(note.transcript, [
      ...payload.vitals.map((v, i) => ({ fieldId: `vital-${i}`, text: v.source_text })),
      ...payload.medications.map((m, i) => ({ fieldId: `med-${i}`, text: m.source_text })),
    ]);
  }, [note.transcript, payload]);

  return (
    <section aria-labelledby="transcript-heading">
      <Card className="overflow-hidden lg:sticky lg:top-[calc(var(--topbar)+1.5rem)]">
        <div className="border-line bg-surface-2 flex items-center justify-between border-b px-6 py-3">
          <h2 id="transcript-heading" className="eyebrow">
            Transcript
          </h2>
          <Pill tone="brand">
            <SparkIcon size={12} />
            {segments.filter((s) => s.fieldId).length} sources linked
          </Pill>
        </div>
        <div className="px-6 py-6">
          {note.transcription_model === "fake-transcriber" && (
            <p
              role="status"
              className="bg-warn-soft text-warn-fg mb-4 rounded-lg px-3 py-2 text-sm"
            >
              <strong>Sample transcript.</strong> No transcription provider is configured, so the
              server substituted a demo sentence instead of your recording. Use the live transcript
              while recording, type the note, or set an OpenAI key.
            </p>
          )}
          <p className="text-ink text-[19px] leading-[1.7]">
            {segments.map((s, i) =>
              s.fieldId ? (
                <mark
                  key={i}
                  onMouseEnter={() => onHover(s.text)}
                  onMouseLeave={() => onHover(null)}
                  className={`rounded-md [box-decoration-break:clone] px-1 py-0.5 text-inherit transition-colors duration-150 ${
                    activeText === s.text.toLowerCase()
                      ? "bg-brand/25 ring-brand-ring ring-2"
                      : "bg-brand-soft ring-brand/20 ring-1"
                  }`}
                >
                  {s.text}
                </mark>
              ) : (
                <span key={i}>{s.text}</span>
              ),
            )}
          </p>
          <p className="border-line text-ink-3 mt-6 border-t pt-4 text-xs leading-relaxed">
            Highlighted words were used for the fields on the right. Hover or focus a field to find
            its words.
          </p>
        </div>
      </Card>
    </section>
  );
}
