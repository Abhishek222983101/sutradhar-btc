import { whenAwake } from "./wake";

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

let entering: Promise<void> | null = null;
/** Demo installs sign visitors in automatically; installs with real accounts fail here quietly and show the login. */
async function ensureSession(): Promise<void> {
  if (session) return;
  entering ??= enterDemo().catch(() => undefined).finally(() => { entering = null; });
  await entering;
}

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  await whenAwake();
  await ensureSession();
  if (session && !path.startsWith("/api/v1/auth") && secondsLeft() < 90) await refresh().catch(() => false);
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  return fetch(`${BASE}${path}`, { ...init, headers });
}

export async function enterDemo(): Promise<void> {
  await whenAwake();
  const r = await fetch(`${BASE}/api/v1/auth/demo`, { method: "POST" });
  if (!r.ok) throw new Error(`demo sign-in failed (${r.status})`);
  save(await r.json());
}

export async function login(email: string, password: string): Promise<void> {
  await whenAwake();
  const r = await fetch(`${BASE}/api/v1/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
  if (!r.ok) throw new Error(r.status === 429 ? "Too many attempts. Wait a few minutes." : "Email or password is incorrect.");
  save(await r.json());
}

let refreshing: Promise<boolean> | null = null;
/** One refresh at a time: the server ends a session when a used refresh token is presented twice, so parallel
 *  requests that all see an expired token must share a single refresh rather than each trying their own. */
function refresh(): Promise<boolean> {
  refreshing ??= doRefresh().finally(() => { refreshing = null; });
  return refreshing;
}

async function doRefresh(): Promise<boolean> {
  if (!session) return false;
  const r = await fetch(`${BASE}/api/v1/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refresh_token }),
  });
  if (!r.ok) return false;
  save(await r.json());
  return true;
}

/** Seconds until the access token expires, read from its (unsigned-checked) payload; used only to renew early. */
function secondsLeft(): number {
  try {
    const exp = JSON.parse(atob(session!.access_token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))).exp as number;
    return exp - Date.now() / 1000;
  } catch { return Infinity; }
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
  await whenAwake();
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
};

/** Fetch a file (an export, a sample pack) as bytes, signed in like every other call. */
export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  let r = await raw(path, init);
  if (r.status === 401 && (await refresh().catch(() => false) || (session?.user.role === "demo" && (await enterDemo().then(() => true, () => false))))) r = await raw(path, init);
  if (!r.ok) throw new Error(`download failed (${r.status})`);
  return r.blob();
}

export type Reason = { family: string; feature: string; value: unknown; contribution: number; text: string };
export type Lead = {
  id: string; run_id: string; type: string; title: string; summary: string; p: number; grade: string; priority: number;
  families: string[]; value_at_risk_sats: number; calibrated: boolean; model_version: string; subject_kind: string; subject_ref: string;
  state: { status: string } | null; reasons?: Reason[];
};
export type Evidence = {
  ip: string | null;
  ips?: { ip: string; n_tx: number }[]; cluster_id: string; addresses: string[];
  transactions: { txid: string; sats: number; candidates: { ip: string; p: number }[]; arrivals: { from: string; sensor: string; dt_ms: number }[] }[];
};
export type Info = {
  mode: string; version: string; database: string; git_sha?: string; time_utc?: string;
  offline_guard: { mode: string; active: boolean; blocked_attempts: number; allow_hosts?: string[] };
  worker?: { embedded: boolean; running: boolean };
  limits?: { upload_max_mb: number; upload_max_rows: number | null; upload_ttl_min: number | null };
};
export type Eval = { seeds: number[]; origin_top1_mean: number; origin_top3_mean: number; origin_random_baseline_mean: number; wallet_cluster_purity_mean: number; observable_transactions_total: number };
export type Dataset = { id: string; name: string; status: string; row_count: number | null; reject_count: number | null; xray: XRay | null };
export type XRay = { rows: number; txs: number; addresses: number; ips: number; network: { observation_model: string; sensors_inferred: number; distinct_src_ips: number; obs_per_tx_p50: number }; quality: Record<string, number>; enabled_stages: string[]; disabled_features: string[]; warnings: string[] };
export type Reject = { file_id: string; row_no: number; rule: string; field: string | null; value: string | null; message: string };
export type Stage = { ms: number; rows: Record<string, number>; notes: string[] };
export type RunInfo = { id: string; status: string; result_digest: string | null; manifest: { stages: Record<string, Stage> } | null };
export type Suggestion = { a: string; b: string; score: number; reasons: string[] };
