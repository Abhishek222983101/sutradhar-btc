import { useEffect, useState } from "react";
import { api, type RunInfo, type Suggestion } from "./api";

type Page<T> = { items: T[]; next_cursor: string | null };
const NAMES: Record<string, string> = {
  E01: "Load", E02: "GeoIP enrichment", E03: "Value flows", E04: "CoinJoin detection", E05: "Wallet clustering",
  E06: "Change-address model", E07: "Peel chains", E08: "Anomaly model", E09: "Origin IP model", E11: "Co-origin linking",
  E12: "Graph embeddings", E13: "Risk propagation", E14: "Behaviour fingerprints", E15: "Motifs", E16: "Merge suggestions",
  E17: "Lead ranking", E19: "Publish",
};
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
                  <small>{s.reasons.join(" · ")}</small></li>
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
              <li key={code}>{NAMES[code] ?? code}: {Object.entries(st.rows).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ") || "done"}
                <small className="mono">{code} · {st.ms} ms{st.notes.length ? ` · ${st.notes.join("; ")}` : ""}</small></li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
