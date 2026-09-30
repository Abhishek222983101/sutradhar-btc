import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Evidence, type Lead } from "./api";
import DataPanel from "./DataPanel";
import PipelinePanel from "./PipelinePanel";

const TYPES = ["ALL", "ACTOR", "CHAIN", "TX"] as const;
const NAMES: Record<string, string> = { ACTOR: "Wallet", CHAIN: "Peel chain", TX: "Unusual tx" };
const btc = (sats: number) => (sats / 1e8).toFixed(4);
const pct = (p: number) => `${Math.round(p * 100)}%`;

type Page<T> = { items: T[]; next_cursor: string | null };

export default function Console({ home }: { home: () => void }) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [type, setType] = useState<(typeof TYPES)[number]>("ALL");
  const [sel, setSel] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [datasetId, setDatasetId] = useState("ds_hero");
  const [runId, setRunId] = useState("run_hero");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const q = type === "ALL" ? "" : `&type=${type}`;
      const page = await api<Page<Lead>>(`/api/v1/runs/${runId}/leads?limit=100${q}`);
      setLeads(page.items);
      setSel((cur) => page.items.find((l) => l.id === cur?.id) ?? page.items[0] ?? null);
    } catch (e) { setError((e as Error).message); }
    setLoading(false);
  }, [type, runId]);
  useEffect(() => { void load(); }, [load]);

  return (
    <div className="wrap console">
      <div className="panel">
        <h2>Leads, most urgent first</h2>
        <div className="chips" role="group" aria-label="Filter by type">
          {TYPES.map((t) => (
            <button key={t} className="chip" aria-pressed={type === t} onClick={() => setType(t)}>{t === "ALL" ? "All" : NAMES[t]}</button>
          ))}
        </div>
        <div className="leads">
          {loading && <div className="empty">Loading…</div>}
          {error && <div className="err">{error}</div>}
          {!loading && !leads.length && !error && <div className="empty">No leads of this type.</div>}
          {leads.map((l) => (
            <button key={l.id} className="lead" aria-current={sel?.id === l.id} onClick={() => setSel(l)}>
              <span className="t">{l.title}</span>
              <span className="m">
                <span className={`grade ${l.grade}`} title={`Grade ${l.grade}`}>{l.grade}</span>
                <span className="bar" aria-hidden="true"><i style={{ width: pct(l.p) }} /></span>
                <b>{pct(l.p)}</b>
              </span>
            </button>
          ))}
        </div>
        <Upload onDone={(d, r) => { setDatasetId(d); setRunId(r); }} />
      </div>
      <div className="detail">
        {sel ? <Detail lead={sel} /> : <div className="panel empty">Select a lead.</div>}
        <PipelinePanel runId={runId} />
        <DataPanel datasetId={datasetId} />
        <p><a href="#/" onClick={home}>Back to the requirement board</a></p>
      </div>
    </div>
  );
}

function Detail({ lead }: { lead: Lead }) {
  const [full, setFull] = useState<Lead | null>(null);
  const [ev, setEv] = useState<Evidence | null>(null);
  useEffect(() => {
    setFull(null); setEv(null);
    void api<Lead>(`/api/v1/leads/${lead.id}`).then(setFull).catch(() => undefined);
    if (lead.subject_kind === "ip_cluster") void api<Evidence>(`/api/v1/leads/${lead.id}/evidence`).then(setEv).catch(() => undefined);
  }, [lead.id, lead.subject_kind]);
  return (
    <>
      <div className="panel">
        <h2>{lead.title}</h2>
        <div className="body">
          <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
            <div><div className="big-p">{pct(lead.p)}</div><div className="note">evidence score</div></div>
            <div><span className={`grade ${lead.grade}`}>{lead.grade}</span> <span className="note">grade</span><br />
              {lead.families.map((f) => <span className="fam" key={f}>{f}</span>)}
            </div>
            {lead.value_at_risk_sats > 0 && <div><b>{btc(lead.value_at_risk_sats)} BTC</b><div className="note">value involved</div></div>}
          </div>
          <p className="hedge">{lead.summary}</p>
          <div>
            <h3 style={{ fontSize: 17, marginBottom: 8 }}>Why this was flagged</h3>
            <ul className="reasons">
              {(full?.reasons ?? []).map((r) => (
                <li key={r.feature}>{r.text}<small className="mono">{r.family} · {r.feature} · weight {r.contribution}</small></li>
              ))}
            </ul>
          </div>
          {!lead.calibrated && <p className="note">This score is a transparent evidence score, not a calibrated probability. Calibration against labelled data is planned.</p>}
        </div>
      </div>
      {ev && <EvidencePanel ev={ev} />}
    </>
  );
}

function EvidencePanel({ ev }: { ev: Evidence }) {
  return (
    <div className="panel">
      <h2>Evidence: {ev.transactions.length} transaction(s) from wallet {ev.cluster_id.slice(0, 10)}…</h2>
      <div className="body">
        <p className="note">{ev.addresses.length} address(es) in this wallet, grouped because they were spent together.</p>
        {ev.transactions.map((t) => <TxCard key={t.txid} tx={t} target={ev.ip} />)}
      </div>
    </div>
  );
}

function TxCard({ tx, target }: { tx: Evidence["transactions"][number]; target: string }) {
  return (
    <div className="tx">
      <div className="mono">tx {tx.txid.slice(0, 16)}… · {btc(tx.sats)} BTC</div>
      <div>
        {tx.candidates.slice(0, 3).map((c) => (
          <div className="cand" key={c.ip}>
            <span className="mono" style={c.ip === target ? { fontWeight: 700 } : undefined}>{c.ip}</span>
            <span className="bar"><i style={{ width: pct(c.p) }} /></span><b>{pct(c.p)}</b>
          </div>
        ))}
      </div>
      <Replay arrivals={tx.arrivals} target={target} />
    </div>
  );
}

// Replays the first announcements of a transaction as sensors heard them. Positions are a stable hash, timing is real.
function Replay({ arrivals, target }: { arrivals: Evidence["transactions"][number]["arrivals"]; target: string }) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const last = Math.max(1, ...arrivals.map((a) => a.dt_ms));
  const raf = useRef(0);
  const reduced = useMemo(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches, []);
  useEffect(() => {
    if (!playing) return;
    const start = performance.now() - (t >= last ? 0 : (t / last) * 2500);
    const tick = (now: number) => {
      const f = Math.min(1, (now - start) / 2500);
      setT(f * last);
      if (f < 1) raf.current = requestAnimationFrame(tick); else setPlaying(false);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);
  const shown = reduced ? last : t;
  const pos = (s: string, salt: number) => { let h = salt; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 997; return 6 + (h / 997) * 88; };
  return (
    <div className="replay">
      <div className="stage" aria-label="Replay of first announcements">
        {arrivals.map((a, i) => (
          <span key={i} className={`dot${a.from === target ? " first" : ""}${a.dt_ms > shown ? " hidden" : ""}`}
            title={`${a.from} → ${a.sensor} at +${a.dt_ms} ms`} style={{ left: `${pos(a.from, 7)}%`, top: `${pos(a.sensor + a.from, 13)}%` }} />
        ))}
      </div>
      <div className="axis">
        <button className="chip" onClick={() => { setT(0); setPlaying(true); }} disabled={reduced}>Replay</button>
        <span className="mono">+{Math.round(shown)} ms of {Math.round(last)} ms · orange = the suspected origin</span>
      </div>
    </div>
  );
}

function Upload({ onDone }: { onDone: (datasetId: string, runId: string) => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (file: File) => {
    setBusy(true); setMsg("Uploading…");
    try {
      const form = new FormData(); form.append("files", file);
      const res = await api<{ dataset: { id: string }; job: { id: string } }>("/api/v1/datasets", { method: "POST", body: form });
      setMsg("Reading and normalising…");
      const job = await poll(res.job.id);
      if (job.status !== "succeeded") throw new Error(job.error ?? "ingest failed");
      const r = job.result as { rows: number; transactions: number; rejects: number; observation_model: string };
      setMsg(`Loaded ${r.rows} rows, ${r.transactions} transactions, ${r.rejects} rejected, observation model: ${r.observation_model}. Running analysis…`);
      const run = await api<{ job: { id: string }; run: { id: string } }>("/api/v1/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: res.dataset.id }) });
      const done = await poll(run.job.id);
      if (done.status !== "succeeded") throw new Error(done.error ?? "analysis failed");
      setMsg(`Done: ${(done.result as { leads: number }).leads} leads found in your upload. It is deleted after 60 minutes.`);
      onDone(res.dataset.id, run.run.id);
    } catch (e) { setMsg((e as Error).message); }
    setBusy(false);
  };
  return (
    <div className="upload">
      <label className="drop">
        <b>Try your own file</b><br /><span className="note">CSV, JSON, NDJSON or XML in the canonical layout, up to 25 MB.</span>
        <input type="file" accept=".csv,.tsv,.txt,.json,.ndjson,.jsonl,.xml" disabled={busy} style={{ display: "block", margin: "8px auto 0" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void send(f); }} />
      </label>
      {msg && <div className="note" role="status">{msg}</div>}
    </div>
  );
}

async function poll(id: string): Promise<{ status: string; error?: string; result?: unknown }> {
  for (let i = 0; i < 240; i++) {
    const j = await api<{ status: string; error?: string; result?: unknown }>(`/api/v1/jobs/${id}`);
    if (["succeeded", "failed", "cancelled"].includes(j.status)) return j;
    await new Promise((r) => setTimeout(r, 750));
  }
  throw new Error("timed out waiting for the job");
}
