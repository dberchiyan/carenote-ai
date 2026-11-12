import { worstFlag } from "./vitals";
import type { Flag } from "../api/types";

export type Reading = { at: string; value: number; flag: Flag; x: number };

export type Cluster = {
  /** Readings in time order. More than one when they were taken too close to draw apart. */
  readings: Reading[];
  /** Plotted at the latest reading: that is the value the nurse acts on. */
  x: number;
  value: number;
  at: string;
  /** The worst flag in the group, so a warning is never hidden behind a later normal value. */
  flag: Flag;
};

/**
 * Merge readings that would be drawn closer than `minGap` (chart units) into one point. Several
 * notes dictated minutes apart otherwise stack into a vertical line of overlapping markers.
 * Readings must be in time order.
 */
export function clusterReadings(readings: Reading[], minGap: number): Cluster[] {
  const groups: Reading[][] = [];
  for (const r of readings) {
    const group = groups[groups.length - 1];
    const first = group?.[0];
    if (group && first && r.x - first.x < minGap) group.push(r);
    else groups.push([r]);
  }
  return groups.map((group) => {
    const latest = group[group.length - 1] as Reading;
    return {
      readings: group,
      x: latest.x,
      value: latest.value,
      at: latest.at,
      flag: worstFlag(group.map((r) => r.flag)),
    };
  });
}
