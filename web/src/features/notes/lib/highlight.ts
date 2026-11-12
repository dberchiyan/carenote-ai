export type Segment = { text: string; fieldId: string | null };

export type Span = { fieldId: string; text: string };

/**
 * Split a transcript into plain and highlighted segments. Each span's `text` is located
 * case-insensitively; overlapping or missing spans are skipped (the field is still editable).
 */
export function highlightSegments(transcript: string, spans: Span[]): Segment[] {
  const lower = transcript.toLowerCase();
  const ranges: { start: number; end: number; fieldId: string }[] = [];
  for (const span of spans) {
    const needle = span.text.trim().toLowerCase();
    if (!needle) continue;
    let from = 0;
    while (from < lower.length) {
      const start = lower.indexOf(needle, from);
      if (start === -1) break;
      const end = start + needle.length;
      if (ranges.every((r) => end <= r.start || start >= r.end)) {
        ranges.push({ start, end, fieldId: span.fieldId });
        break;
      }
      from = start + 1;
    }
  }
  ranges.sort((a, b) => a.start - b.start);

  const segments: Segment[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start > cursor) segments.push({ text: transcript.slice(cursor, r.start), fieldId: null });
    segments.push({ text: transcript.slice(r.start, r.end), fieldId: r.fieldId });
    cursor = r.end;
  }
  if (cursor < transcript.length) segments.push({ text: transcript.slice(cursor), fieldId: null });
  return segments;
}
