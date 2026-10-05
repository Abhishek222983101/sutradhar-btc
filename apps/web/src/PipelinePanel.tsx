import { useEffect, useState } from "react";
import { api, role, type RunInfo, type Suggestion } from "./api";
import { STAGE_NAMES as NAMES } from "./stages";

type Page<T> = { items: T[]; next_cursor: string | null };

const ROW_LABEL: Record<string, string> = { d_addr: "addresses", d_ip: "IPs", d_tx: "transactions", d_cluster: "wallet groups" };
const label = (k: string) => ROW_LABEL[k] ?? k.replace(/^d_/, "").replace(/_/g, " ");
const short = (c: string) => `${c.slice(0, 10)}…`;

// What the engine did for this run (every stage, its output and time), and which wallets it thinks belong together.
export default function PipelinePanel({ runId }: { runId: string }) {
  const [run, setRun] = useState<RunInfo | null>(null);
  const [sug, setSug] = useState<Suggestion[]>([]);
  useEffect(() => {
    setRun(null); setSug([]);
    void api<RunInfo>(`/api/v1/runs/${runId}`).then(setRun).catch(() => undefined);
    void api<Page<Suggestion>>(`/api/v1/runs/${runId}/suggestions?limit=6`).then((p) => setSug(p.items)).catch(() => undefined);
  }, [runId]);
  const [decided, setDecided] = useState<Record<string, string>>({});
  const decide = async (s: Suggestion, decision: "accept" | "reject") => {
    const reason = window.prompt(`Why ${decision}? (kept in the audit log)`, decision === "accept" ? "Shared origin IP and similar behaviour" : "Different operators");
    if (!reason) return;
    try {
      await api("/api/v1/merge-decisions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: runId, a: s.a, b: s.b, decision, reason }) });
      setDecided((d) => ({ ...d, [s.a + s.b]: decision }));
    } catch (e) { window.alert((e as Error).message); }
  };
  const stages = Object.entries(run?.manifest?.stages ?? {}).sort(([a], [b]) => a.localeCompare(b));
  if (!run) return null;
  return (
    <>
      {sug.length > 0 && (
        <div className="panel">
          <h2>Wallets that may belong to one operator</h2>
          <div className="body">
            <p className="note">Suggestions for an analyst to accept or reject. Nothing is merged automatically.</p>
            <ul className="reasons">
              {sug.map((s) => (
                <li key={s.a + s.b}><b>{short(s.a)}</b> and <b>{short(s.b)}</b> (score {Math.round(s.score * 100)}%)
                  <small>{s.reasons.join(" · ")}</small>
                  {role() === "lead" && (decided[s.a + s.b]
                    ? <small><b>You chose: {decided[s.a + s.b]}</b></small>
                    : <span><button className="chip" onClick={() => void decide(s, "accept")}>Accept</button> <button className="chip" onClick={() => void decide(s, "reject")}>Reject</button></span>)}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <div className="panel">
        <h2>What the engine did</h2>
        <div className="body">
          <p className="note mono">result digest {run.result_digest?.slice(0, 16)}…, identical for identical input</p>
          <ul className="reasons">
            {stages.map(([code, st]) => (
              <li key={code}>{NAMES[code] ?? code}: {Object.entries(st.rows).map(([k, v]) => `${v} ${label(k)}`).join(", ") || "done"}
                <small className="mono">{code} · {st.ms} ms{st.notes.length ? ` · ${st.notes.join("; ")}` : ""}</small></li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
