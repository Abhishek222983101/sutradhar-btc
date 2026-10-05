import { useEffect, useState } from "react";
import { api } from "./api";

export type Fetched<T> = { data: T | null; error: string; loading: boolean; reload: () => void };

/** Load one API path; `null` skips. Stale responses from a previous path are ignored. */
export function useApi<T>(path: string | null): Fetched<T> {
  const [state, set] = useState<{ data: T | null; error: string; loading: boolean }>({ data: null, error: "", loading: path !== null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (path === null) { set({ data: null, error: "", loading: false }); return; }
    let live = true;
    set((s) => ({ ...s, loading: true, error: "" }));
    api<T>(path).then(
      (data) => { if (live) set({ data, error: "", loading: false }); },
      (e: unknown) => { if (live) set({ data: null, error: (e as Error).message, loading: false }); },
    );
    return () => { live = false; };
  }, [path, tick]);
  return { ...state, reload: () => setTick((n) => n + 1) };
}
