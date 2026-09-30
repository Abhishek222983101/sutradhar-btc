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
export const role = (): string | null => session?.user.role ?? null;

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

export async function login(email: string, password: string): Promise<void> {
  const r = await fetch(`${BASE}/api/v1/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
  if (!r.ok) throw new Error(r.status === 429 ? "Too many attempts. Wait a few minutes." : "Email or password is incorrect.");
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
  if (r.status === 401 && (await refresh().catch(() => false) || (session?.user.role === "demo" && (await enterDemo().then(() => true, () => false))))) r = await raw(path, init);
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
  ip: string | null;
  ips?: { ip: string; n_tx: number }[]; cluster_id: string; addresses: string[];
  transactions: { txid: string; sats: number; candidates: { ip: string; p: number }[]; arrivals: { from: string; sensor: string; dt_ms: number }[] }[];
};
export type Info = { mode: string; version: string; database: string; offline_guard: { mode: string; active: boolean; blocked_attempts: number } };
export type Eval = { seeds: number[]; origin_top1_mean: number; origin_top3_mean: number; origin_random_baseline_mean: number; wallet_cluster_purity_mean: number; observable_transactions_total: number };
export type Dataset = { id: string; name: string; status: string; row_count: number | null; reject_count: number | null; xray: XRay | null };
export type XRay = { rows: number; txs: number; addresses: number; ips: number; network: { observation_model: string; sensors_inferred: number; distinct_src_ips: number; obs_per_tx_p50: number }; quality: Record<string, number>; enabled_stages: string[]; disabled_features: string[]; warnings: string[] };
export type Reject = { file_id: string; row_no: number; rule: string; field: string | null; value: string | null; message: string };
export type Stage = { ms: number; rows: Record<string, number>; notes: string[] };
export type RunInfo = { id: string; status: string; result_digest: string | null; manifest: { stages: Record<string, Stage> } | null };
export type Suggestion = { a: string; b: string; score: number; reasons: string[] };
