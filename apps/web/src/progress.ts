import { useSyncExternalStore } from "react";

// The visitor's place in the guided tour. A per-browser convenience only: it never reaches the server, and every
// read and write tolerates blocked storage (private windows, embedded browsers).
const KEY = "sutradhar.guide.v1";

export type Progress = { done: string[]; current: string; hidden: boolean; collapsed: boolean; helpClosed: string[] };
const FRESH: Progress = { done: [], current: "leads", hidden: false, collapsed: false, helpClosed: ["console"] };

function read(): Progress {
  try {
    return { ...FRESH, ...(JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Progress>) };
  } catch {
    return FRESH;
  }
}

let snap = read();
const subs = new Set<() => void>();

export function update(patch: Partial<Progress>) {
  snap = { ...snap, ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(snap)); } catch { /* storage blocked */ }
  subs.forEach((f) => f());
}

export function toggleDone(id: string) {
  update({ done: snap.done.includes(id) ? snap.done.filter((d) => d !== id) : [...snap.done, id] });
}

export function useProgress(): Progress {
  return useSyncExternalStore((cb) => { subs.add(cb); return () => subs.delete(cb); }, () => snap);
}
