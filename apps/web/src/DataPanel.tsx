import { useEffect, useState } from "react";
import { api, type Dataset, type Reject, type XRay } from "./api";

type Page<T> = { items: T[]; next_cursor: string | null };
const RULES: Record<string, string> = {
  V01: "Bad transaction id", V02: "Bad IP address", V03: "Port out of range", V04: "Bad timestamp",
  V05: "Array lengths differ", V06: "Bad amount", V07: "No outputs", V08: "Outputs exceed inputs",
  V10: "Conflicting duplicate", V12: "Implausible address",
};

// The dataset X-ray (what the data allows the engine to do) and the rejects report (what was refused and why).
export default function DataPanel({ datasetId }: { datasetId: string }) {
  const [ds, setDs] = useState<Dataset | null>(null);
  const [rejects, setRejects] = useState<Reject[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    setErr("");
    void api<Dataset>(`/api/v1/datasets/${datasetId}`).then(setDs).catch((e) => setErr((e as Error).message));
    void api<Page<Reject>>(`/api/v1/datasets/${datasetId}/rejects?limit=20`).then((p) => setRejects(p.items)).catch(() => undefined);
  }, [datasetId]);
  if (err) return <div className="err">{err}</div>;
  if (!ds?.xray) return <div className="empty">Loading dataset details…</div>;
  const x: XRay = ds.xray;
  return (
    <div className="panel">
      <h2>Dataset X-ray: {ds.name}</h2>
      <div className="body">
        <div className="stats" style={{ margin: 0 }}>
          <div className="stat"><b>{x.rows}</b><span>observations</span></div>
          <div className="stat"><b>{x.txs}</b><span>transactions</span></div>
          <div className="stat"><b>{x.addresses}</b><span>addresses</span></div>
          <div className="stat"><b>{x.ips}</b><span>IP addresses</span></div>
        </div>
        <p>
          Network view: <b>{x.network.observation_model}</b>, {x.network.sensors_inferred} listening sensor(s) detected,
          about {x.network.obs_per_tx_p50} sightings per transaction.
        </p>
        <p className="note">Analysis steps enabled: {x.enabled_stages.join(", ")}.</p>
        {x.disabled_features.map((d) => <p className="hedge" key={d}>Switched off: {d}</p>)}
        {x.warnings.map((w) => <p className="hedge" key={w}>{w}</p>)}
        <h3 style={{ fontSize: 17 }}>Rows refused: {ds.reject_count ?? 0}</h3>
        {rejects.length === 0 ? <p className="note">Every row passed validation.</p> : (
          <ul className="reasons">
            {rejects.map((r, i) => (
              <li key={i}>{RULES[r.rule] ?? r.rule}: {r.message}
                <small className="mono">row {r.row_no} · {r.rule}{r.field ? ` · ${r.field}` : ""}{r.value ? ` · ${r.value}` : ""}</small></li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
