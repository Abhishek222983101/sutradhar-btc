import { useSyncExternalStore } from "react";

// The demo API lives on a free host that sleeps after 15 idle minutes and takes 30-45 s to wake. Judges must never
// read that as "broken": one shared probe tracks the server's state, every request waits for it, and the header says
// what is happening. While a visitor keeps the tab open, a heartbeat stops the host from going back to sleep.
const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export type WakeState = "checking" | "waking" | "ready" | "down";
export type Wake = { state: WakeState; elapsed: number; snapshot: boolean; epoch: number };

const SLOW_AFTER_MS = 2500;
const GIVE_UP_MS = 150_000;
const HEARTBEAT_MS = 4 * 60_000;

let snap: Wake = { state: "checking", elapsed: 0, snapshot: false, epoch: 0 };
const subs = new Set<() => void>();
let running: Promise<void> | null = null;
let heartbeat: number | undefined;

const set = (patch: Partial<Wake>) => {
  const next = { ...snap, ...patch };
  // Coming alive after serving the saved snapshot: bump the epoch so pages reload with live data.
  if (patch.state === "ready" && snap.state !== "ready" && snap.snapshot) { next.epoch = snap.epoch + 1; next.snapshot = false; }
  snap = next;
  subs.forEach((f) => f());
};

/** A page was just served from the saved snapshot while the live server is not ready. */
export function markSnapshot() { if (!snap.snapshot) set({ snapshot: true }); }
export const isReady = () => snap.state === "ready";

async function ping(timeoutMs: number): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
    return r.ok;
  } catch {
    return false;
  }
}

function startHeartbeat() {
  if (heartbeat !== undefined) return;
  heartbeat = window.setInterval(async () => {
    if (document.visibilityState === "hidden") return;
    if (!(await ping(20_000))) {
      set({ state: "checking", elapsed: 0 });
      running = null;
      void probe();
    }
  }, HEARTBEAT_MS);
}

export function probe(): Promise<void> {
  if (running) return running;
  const t0 = Date.now();
  set({ state: "checking", elapsed: 0 });
  const tick = window.setInterval(() => {
    const elapsed = Math.round((Date.now() - t0) / 1000);
    set({ state: Date.now() - t0 > SLOW_AFTER_MS ? "waking" : "checking", elapsed });
  }, 1000);
  running = (async () => {
    try {
      while (Date.now() - t0 < GIVE_UP_MS) {
        if (await ping(25_000)) {
          set({ state: "ready", elapsed: Math.round((Date.now() - t0) / 1000) });
          startHeartbeat();
          return;
        }
        await new Promise((r) => setTimeout(r, 3000));
      }
      set({ state: "down", elapsed: Math.round((Date.now() - t0) / 1000) });
      throw new Error("The demo server did not answer.");
    } finally {
      window.clearInterval(tick);
      if (snap.state !== "ready") running = null;
    }
  })();
  return running;
}

export function whenAwake(): Promise<void> {
  return snap.state === "ready" ? Promise.resolve() : probe();
}

export function retry() {
  running = null;
  void probe().catch(() => undefined);
}

export function useWake(): Wake {
  return useSyncExternalStore(
    (cb) => {
      subs.add(cb);
      return () => subs.delete(cb);
    },
    () => snap,
  );
}
