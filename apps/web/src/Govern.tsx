import { useEffect, useState } from "react";
import { api } from "./api";

type Model = { name: string; version: string; metrics: Record<string, number>; trained_on: Record<string, unknown> };
type Setting = { key: string; value: unknown; default: unknown; changed: boolean };
type AuditRow = { seq: number; ts: string; actor_role: string; action: string; target_kind: string; target_ref: string };

export default function Govern() {
  const [models, setModels] = useState<Model[]>([]);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [verify, setVerify] = useState<{ ok: boolean; entries: number } | null>(null);
  useEffect(() => {
    void api<Model[]>("/api/v1/models").then(setModels).catch(() => undefined);
    void api<Setting[]>("/api/v1/settings").then(setSettings).catch(() => undefined);
    void api<{ items: AuditRow[] }>("/api/v1/audit?limit=30").then((p) => setAudit(p.items)).catch(() => undefined);
    void api<{ ok: boolean; entries: number }>("/api/v1/audit/verify").then(setVerify).catch(() => undefined);
  }, []);
  return (
    <div className="wrap">
      <h2 className="section-title">Govern</h2>
      <div className="board">
        {models.map((m) => (
          <article className="req" key={m.name}>
            <header><h3>{m.name}</h3><span className="st live">{m.version}</span></header>
            <p>{Object.entries(m.metrics).slice(0, 3).map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(3) : v}`).join(" · ")}</p>
          </article>
        ))}
      </div>
      {verify && (
        <p className={verify.ok ? "note" : "err"}>Audit chain: {verify.ok ? "verified" : "BROKEN"} ({verify.entries} entries)</p>
      )}
      <h3 style={{ fontSize: 19, marginTop: 24 }}>Settings ({settings.filter((s) => s.changed).length} changed from default)</h3>
      <div className="panel"><div className="body">
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {settings.map((s) => (
              <tr key={s.key} style={{ borderBottom: "1px solid #ccc" }}>
                <td className="mono" style={{ padding: 4 }}>{s.key}</td>
                <td className="mono" style={{ padding: 4 }}>{JSON.stringify(s.value)}</td>
                <td style={{ padding: 4 }}>{s.changed && <span className="st warn">changed</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div></div>
      <h3 style={{ fontSize: 19, marginTop: 24 }}>Recent audit activity</h3>
      <div className="panel"><div className="body">
        <ul className="reasons">
          {audit.map((a) => <li key={a.seq}>#{a.seq} {a.action} on {a.target_kind}:{a.target_ref.slice(0, 20)}<small>{a.actor_role} · {new Date(a.ts).toLocaleString()}</small></li>)}
        </ul>
      </div></div>
    </div>
  );
}
