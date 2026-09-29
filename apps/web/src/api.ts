const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const KEY = "sutradhar.session";

export type Session = { access_token: string; refresh_token: string; user: { role: string; name: string } };
let session: Session | null = null;
try { session = JSON.parse(sessionStorage.getItem(KEY) ?? "null"); } catch { session = null; }

const save = (s: Session | null) => {
  session = s;
  try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY); } catch { /* private mode */ }
};
export const hasSession = () => session !== null;

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  return fetch(`${BASE}${path}`, { ...init, headers });
}

export async function enterDemo(): Promise<void> {
  const r = await fetch(`${BASE}/api/v1/auth/demo`, { method: "POST" });
  if (!r.ok) throw new Error(`demo sign-in failed (${r.status})`);
  save(await r.json());
}

async function refresh(): Promise<boolean> {
  if (!session) return false;
  const r = await fetch(`${BASE}/api/v1/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refresh_token }),
  });
  if (!r.ok) return false;
  save(await r.json());
  return true;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let r = await raw(path, init);
  if (r.status === 401 && (await refresh().catch(() => false) || (await enterDemo().then(() => true, () => false)))) r = await raw(path, init);
  if (!r.ok) {
    const p = await r.json().catch(() => ({}));
    throw new Error(p.detail || `request failed (${r.status})`);
  }
  return r.json();
}

export const publicGet = async <T,>(path: string): Promise<T> => {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
};

export type Reason = { family: string; feature: string; value: unknown; contribution: number; text: string };
export type Lead = {
  id: string; run_id: string; type: string; title: string; summary: string; p: number; grade: string; priority: number;
  families: string[]; value_at_risk_sats: number; calibrated: boolean; model_version: string; subject_kind: string;
  state: { status: string } | null; reasons?: Reason[];
};
export type Evidence = {
  ip: string; cluster_id: string; addresses: string[];
  transactions: { txid: string; sats: number; candidates: { ip: string; p: number }[]; arrivals: { from: string; sensor: string; dt_ms: number }[] }[];
};
export type Info = { mode: string; version: string; database: string; offline_guard: { mode: string; active: boolean; blocked_attempts: number } };
export type Eval = Record<string, number | string>;
