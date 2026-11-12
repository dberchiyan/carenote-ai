"use client";

import { useCallback, useSyncExternalStore } from "react";

import type { GuideEvent } from "./steps";

/*
 * Guide progress is a per-viewer convenience: it lives in this browser only (localStorage), keyed
 * by user, and every read and write tolerates storage being blocked.
 */

const CHANGE = "carenote:guide-change";
const EVENT = "carenote:guide-event";
const key = (userId: string) => `carenote.guide.v1.${userId}`;

type Stored = { done: string[]; seen: boolean };
const EMPTY: Stored = { done: [], seen: false };
const cache = new Map<string, { raw: string | null; value: Stored }>();

function read(userId: string): Stored {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(key(userId));
  } catch {
    // Storage blocked: the guide still works for this page view.
  }
  const hit = cache.get(userId);
  if (hit && hit.raw === raw) return hit.value; // same snapshot object while nothing changed
  let value = EMPTY;
  try {
    const parsed = raw ? (JSON.parse(raw) as Partial<Stored>) : null;
    if (parsed)
      value = { done: Array.isArray(parsed.done) ? parsed.done : [], seen: !!parsed.seen };
  } catch {
    value = EMPTY;
  }
  cache.set(userId, { raw, value });
  return value;
}

function write(userId: string, value: Stored): void {
  try {
    localStorage.setItem(key(userId), JSON.stringify(value));
  } catch {
    cache.set(userId, { raw: null, value });
  }
  window.dispatchEvent(new Event(CHANGE));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Tell the guide the viewer did something worth a tick (confirmed a note, exported FHIR…). */
export function markGuideStep(event: GuideEvent): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<GuideEvent>(EVENT, { detail: event }));
}

export function onGuideEvent(listener: (event: GuideEvent) => void): () => void {
  const handler = (e: Event) => listener((e as CustomEvent<GuideEvent>).detail);
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}

export function useGuideProgress(userId: string) {
  const state = useSyncExternalStore(
    subscribe,
    () => read(userId),
    () => EMPTY,
  );
  const complete = useCallback(
    (id: string) => {
      const current = read(userId);
      if (!current.done.includes(id)) write(userId, { ...current, done: [...current.done, id] });
    },
    [userId],
  );
  const markSeen = useCallback(() => {
    const current = read(userId);
    if (!current.seen) write(userId, { ...current, seen: true });
  }, [userId]);
  const reset = useCallback(() => write(userId, { done: [], seen: true }), [userId]);
  /** True exactly once per viewer: reads storage directly, not the pre-hydration snapshot. */
  const firstVisit = useCallback(() => {
    if (read(userId).seen) return false;
    markSeen();
    return true;
  }, [userId, markSeen]);
  return { done: new Set(state.done), complete, firstVisit, reset };
}
