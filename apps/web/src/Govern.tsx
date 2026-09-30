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

  const changed = settings.filter((s) => s.changed).length;

  return (
    <div className="wrap">
      <section style={{ paddingTop: 32 }}>
        <h2 className="section-title">Govern</h2>
        <p className="note">Models, thresholds and the audit trail — everything a decision in this system rests on.</p>
      </section>

      <section style={{ marginTop: 8 }}>
        <h3 style={{ fontSize: 18, marginBottom: 10 }}>Model registry</h3>
        <div className="board">
          {models.map((m) => (
            <article className="req" key={m.name}>
              <header>
                <h3>{m.name}</h3>
                <span className="st live">{m.version}</span>
              </header>
              <p>
                {Object.entries(m.metrics)
                  .slice(0, 3)
                  .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "number" ? v.toFixed(3) : v}`)
                  .join(" · ") || "No held-out metrics recorded for this model."}
              </p>
            </article>
          ))}
          {models.length === 0 && <p className="note">Loading model registry…</p>}
        </div>
      </section>

      <section style={{ marginTop: 28 }}>
        <h3 style={{ fontSize: 18, marginBottom: 10 }}>Audit chain</h3>
        {verify && (
          <p className={verify.ok ? "hedge" : "err"}>
            {verify.ok ? "✓ Verified" : "✗ BROKEN"} — {verify.entries} entries, recomputed from scratch on every check.
          </p>
        )}
      </section>

      <section className="two-col" style={{ marginTop: 24, alignItems: "stretch" }}>
        <div className="panel">
          <h2>
            Settings <span className="note" style={{ fontWeight: 400 }}>({changed} changed from default)</span>
          </h2>
          <div className="body" style={{ maxHeight: 420, overflow: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Value</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {settings.map((s) => (
                  <tr key={s.key}>
                    <td className="mono">{s.key}</td>
                    <td className="mono num">{JSON.stringify(s.value)}</td>
                    <td>{s.changed && <span className="st part">changed</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <h2>Recent activity</h2>
          <div className="body" style={{ maxHeight: 420, overflow: "auto" }}>
            <ul className="reasons">
              {audit.map((a) => (
                <li key={a.seq}>
                  <span className="mono">#{a.seq}</span> {a.action.replace(/\./g, " · ")} on {a.target_kind}:
                  {a.target_ref.slice(0, 18)}
                  <small>
                    {a.actor_role} · {new Date(a.ts).toLocaleString()}
                  </small>
                </li>
              ))}
              {audit.length === 0 && <li className="note">No audit entries yet.</li>}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
