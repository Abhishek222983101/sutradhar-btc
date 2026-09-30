import { useEffect, useState } from "react";
import { api, role } from "./api";
import { t, type Lang } from "./i18n";

type Model = { name: string; version: string; metrics: Record<string, number>; trained_on: Record<string, unknown> };
type Setting = { key: string; value: unknown; default: unknown; changed: boolean };
type AuditRow = { seq: number; ts: string; actor_role: string; action: string; target_kind: string; target_ref: string };

const formatMetric = (v: unknown): string => {
  if (typeof v !== "number") return String(v);
  return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3);
};

export default function Govern({ lang = "en" }: { lang?: Lang } = {}) {
  const [models, setModels] = useState<Model[]>([]);
  const [settings, setSettings] = useState<Setting[]>([]);
  const [audit, setAudit] = useState<AuditRow[] | null>(null);
  const [verify, setVerify] = useState<{ ok: boolean; entries: number } | null>(null);
  useEffect(() => {
    void api<Model[]>("/api/v1/models").then(setModels).catch(() => undefined);
    void api<Setting[]>("/api/v1/settings").then(setSettings).catch(() => undefined);
    void api<{ items: AuditRow[] }>("/api/v1/audit?limit=30").then((p) => setAudit(p.items)).catch(() => setAudit([]));
    void api<{ ok: boolean; entries: number }>("/api/v1/audit/verify").then(setVerify).catch(() => undefined);
  }, []);

  const changed = settings.filter((s) => s.changed).length;

  return (
    <div className="wrap">
      <section style={{ paddingTop: 32 }}>
        <h2 className="section-title">{t(lang, "Govern")}</h2>
        <p className="note">Models, thresholds and the audit trail — everything a decision in this system rests on.</p>
      </section>

      <section style={{ marginTop: 8 }}>
        <h3 style={{ fontSize: 18, marginBottom: 10 }}>{t(lang, "Model registry")}</h3>
        <p className="small-note">Row/actor counts are training-set sizes, not scores — see docs/EVAL.md for held-out accuracy.</p>
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
                  .map(([k, v]) => `${k.replace(/_/g, " ")}: ${formatMetric(v)}`)
                  .join(" · ") || "No held-out metrics recorded for this model."}
              </p>
            </article>
          ))}
          {models.length === 0 && <p className="note">Loading model registry…</p>}
        </div>
      </section>

      <section style={{ marginTop: 28 }}>
        <h3 style={{ fontSize: 18, marginBottom: 10 }}>{t(lang, "Audit chain")}</h3>
        {!["lead", "admin", "auditor"].includes(role() ?? "") ? (
          <p className="small-note">Chain verification needs a lead analyst, admin or auditor role.</p>
        ) : verify ? (
          <p className={verify.ok ? "hedge" : "err"}>
            {verify.ok ? "✓ Verified" : "✗ BROKEN"} — {verify.entries} entries, recomputed from scratch on every check.
          </p>
        ) : (
          <p className="small-note">Verifying…</p>
        )}
      </section>

      <section className="two-col" style={{ marginTop: 24, alignItems: "stretch" }}>
        <div className="panel">
          <h2>
            {t(lang, "Settings")} <span className="note" style={{ fontWeight: 400 }}>({changed} changed from default)</span>
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
          <h2>{t(lang, "Recent activity")}</h2>
          <div className="body" style={{ maxHeight: 420, overflow: "auto" }}>
            {!["lead", "admin", "auditor"].includes(role() ?? "") ? (
              <p className="small-note">Audit access needs a lead analyst, admin or auditor role — you're signed in as {role() ?? "a visitor"}.</p>
            ) : audit === null ? (
              <p className="small-note">Loading…</p>
            ) : audit.length === 0 ? (
              <p className="small-note">No audit entries yet.</p>
            ) : (
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
              </ul>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
