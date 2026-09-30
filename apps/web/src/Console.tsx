import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Evidence, type Lead } from "./api";
import DataPanel from "./DataPanel";
import { btc, pct, pctPair } from "./format";
import LinkGraph from "./LinkGraph";
import Canvas from "./Canvas";
import Dossier from "./Dossier";
import PipelinePanel from "./PipelinePanel";
import SearchBox from "./SearchBox";

const TYPES = ["ALL", "ACTOR", "CHAIN", "TX"] as const;
const NAMES: Record<string, string> = { ACTOR: "Wallet", CHAIN: "Peel chain", TX: "Unusual tx" };

type Page<T> = { items: T[]; next_cursor: string | null };

export default function Console({ home }: { home: () => void }) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [type, setType] = useState<(typeof TYPES)[number]>("ALL");
  const [sel, setSel] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [datasetId, setDatasetId] = useState("ds_hero");
  const [runId, setRunId] = useState("run_hero");
  const [dossier, setDossier] = useState<{ kind: string; ref: string } | null>(null);

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
        <div style={{ padding: "10px 14px" }}>
          <SearchBox
            runId={runId}
            onOpen={(kind, ref) => {
              if (kind === "lead") {
                const found = leads.find((l) => l.id === ref);
                if (found) { setSel(found); setDossier(null); }
              } else {
                setDossier({ kind, ref });
              }
            }}
          />
        </div>
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
        {dossier ? (
          <Dossier runId={runId} kind={dossier.kind} ref={dossier.ref} close={() => setDossier(null)} />
        ) : sel ? (
          <Detail lead={sel} runId={runId} />
        ) : (
          <div className="panel empty">Select a lead, or search above.</div>
        )}
        <PipelinePanel runId={runId} />
        <DataPanel datasetId={datasetId} />
        <p><a href="#/" onClick={home}>Back to the requirement board</a></p>
      </div>
    </div>
  );
}

type Explanation = { reasons: { family: string; feature: string; text: string; contribution: number }[]; opposing: { text: string }[]; counterfactual: { feature: string; p_after: number; p_before: number }[]; priority: Record<string, number> };

function Detail({ lead, runId }: { lead: Lead; runId: string }) {
  const [full, setFull] = useState<Lead | null>(null);
  const [ev, setEv] = useState<Evidence | null>(null);
  const [explain, setExplain] = useState<Explanation | null>(null);
  const [showCanvas, setShowCanvas] = useState(false);
  const [caseMsg, setCaseMsg] = useState("");
  useEffect(() => {
    setFull(null); setEv(null); setExplain(null); setShowCanvas(false); setCaseMsg("");
    void api<Lead>(`/api/v1/leads/${lead.id}`).then(setFull).catch(() => undefined);
    void api<Explanation>(`/api/v1/leads/${lead.id}/explanation`).then(setExplain).catch(() => undefined);
    if (["cluster", "ip", "cashout"].includes(lead.subject_kind)) void api<Evidence>(`/api/v1/leads/${lead.id}/evidence`).then(setEv).catch(() => undefined);
  }, [lead.id, lead.subject_kind]);
  const addToCase = async () => {
    try {
      const cases = await api<{ items: { id: string; title: string }[] }>("/api/v1/cases?limit=1");
      let caseId = cases.items[0]?.id;
      if (!caseId) {
        const c = await api<{ id: string }>("/api/v1/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "Working case" }) });
        caseId = c.id;
      }
      await api(`/api/v1/cases/${caseId}/items`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_kind: "lead", ref: lead.id, run_id: runId }) });
      setCaseMsg("Added to case — see the Cases tab.");
    } catch (e) { setCaseMsg((e as Error).message); }
  };
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
            <div className="lead-actions">
              {lead.subject_kind === "cluster" && <button className="chip" onClick={() => setShowCanvas((v) => !v)}>{showCanvas ? "Hide" : "Investigate"} graph</button>}
              <button className="chip" onClick={() => void addToCase()}>Add to case</button>
            </div>
          </div>
          {caseMsg && <p className="note">{caseMsg}</p>}
          <p className="hedge">{lead.summary}</p>
          <div>
            <h3 style={{ fontSize: 17, marginBottom: 8 }}>Why this was flagged</h3>
            <ul className="reasons">
              {(full?.reasons ?? []).map((r) => (
                <li key={r.feature}>{r.text}<small className="mono">{r.family} · {r.feature} · weight {r.contribution}</small></li>
              ))}
            </ul>
          </div>
          {explain && explain.opposing.length > 0 && (
            <div>
              <h3 style={{ fontSize: 17, marginBottom: 8 }}>Against this reading</h3>
              <ul className="reasons">{explain.opposing.map((o, i) => <li key={i}>{o.text}</li>)}</ul>
            </div>
          )}
          {explain && explain.counterfactual.length > 0 && (
            <div>
              <h3 style={{ fontSize: 17, marginBottom: 8 }}>What would clear this</h3>
              <ul className="reasons">
                {explain.counterfactual.map((c, i) => {
                  const [before, after] = pctPair(c.p_before, c.p_after);
                  return (
                    <li key={i}>If <span className="mono">{c.feature}</span> were typical, the score would move from {before} to {after}.</li>
                  );
                })}
              </ul>
            </div>
          )}
          {explain && Object.keys(explain.priority).length > 0 && (
            <p className="note mono">priority = {Object.entries(explain.priority).map(([k, v]) => `${k} ${v}`).join(" × ")}</p>
          )}
          {!lead.calibrated && <p className="note">This score is a transparent evidence score, not a calibrated probability for TX/CHAIN leads; ACTOR/CASHOUT/IP leads use the calibrated model.</p>}
        </div>
      </div>
      {showCanvas && lead.subject_kind === "cluster" && <Canvas runId={runId} clusterId={lead.id} />}
      {ev && <EvidencePanel ev={ev} />}
    </>
  );
}

function EvidencePanel({ ev }: { ev: Evidence }) {
  return (
    <div className="panel">
      <h2>Evidence: {ev.transactions.length} transaction(s) from wallet {ev.cluster_id.slice(0, 10)}…</h2>
      <div className="body">
        <p className="note">{ev.addresses.length} address(es) in this wallet, grouped because they were spent together. Thicker lines mean the IP is more likely the first sender.</p>
        <LinkGraph ev={ev} />
        {ev.transactions.map((t) => <TxCard key={t.txid} tx={t} target={ev.ip ?? ""} />)}
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
