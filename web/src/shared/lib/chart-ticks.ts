/**
 * Which points get an x-axis label. One label per calendar day, at most `max`, and never two
 * labels closer than `minGap` (in the chart's own units), so dense same-day readings do not print
 * "Nov 11" on top of "Nov 11".
 */
export function xTickIndices(
  times: number[],
  xs: number[],
  { max = 5, minGap = 56 }: { max?: number; minGap?: number } = {},
): number[] {
  if (times.length === 0) return [];
  const firstOfDay: number[] = [];
  let lastDay = "";
  times.forEach((t, i) => {
    const day = new Date(t).toDateString();
    if (day !== lastDay) {
      firstOfDay.push(i);
      lastDay = day;
    }
  });
  // Keep the last reading's day label at the right edge when it is a different day.
  let picked = firstOfDay;
  if (picked.length > max) {
    const step = (picked.length - 1) / (max - 1);
    picked = Array.from({ length: max }, (_, k) => firstOfDay[Math.round(k * step)]).filter(
      (i): i is number => i !== undefined,
    );
  }
  const kept: number[] = [];
  for (const i of picked) {
    const prev = kept.at(-1);
    if (prev === undefined || (xs[i] ?? 0) - (xs[prev] ?? 0) >= minGap) kept.push(i);
  }
  return kept;
}
