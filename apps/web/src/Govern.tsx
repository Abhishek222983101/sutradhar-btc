import { role } from "./api";
import { useApi } from "./hooks";
import { t, type Lang } from "./i18n";
import { Callout, HowTo, PageHeader, Skeleton } from "./ui";

type Model = { name: string; version: string; metrics: Record<string, number>; trained_on: Record<string, unknown> };
type Setting = { key: string; value: unknown; default: unknown; changed: boolean };
type AuditRow = { seq: number; ts: string; actor_role: string; action: string; target_kind: string; target_ref: string };
type Verify = { ok: boolean; entries: number; head: string | null };

const formatMetric = (v: unknown): string => {
  if (typeof v !== "number") return String(v);
  return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3);
};
const CAN_READ_AUDIT = ["lead", "admin", "auditor"];

export default function Govern({ lang = "en" }: { lang?: Lang } = {}) {
  const models = useApi<Model[]>("/api/v1/models");
  const settings = useApi<Setting[]>("/api/v1/settings");
  const verify = useApi<Verify>("/api/v1/audit/verify");
  const canRead = CAN_READ_AUDIT.includes(role() ?? "");
  const audit = useApi<{ items: AuditRow[] }>(canRead ? "/api/v1/audit?limit=30" : null);
  const changed = (settings.data ?? []).filter((s) => s.changed).length;

  return (
    <div className="wrap page">
      <PageHeader
        kicker="Governance · requirement R-07"
        title={t(lang, "Govern")}
        lede="Models, thresholds and the audit trail: everything a decision in this system rests on."
      />
      <HowTo page="govern" />

      <section aria-labelledby="models">
        <h2 id="models" className="section-title">{t(lang, "Model registry")}</h2>
        <p className="section-sub">Counts are training-set sizes, not scores. Held-out accuracy for each model is in docs/EVAL.md and on the How it works page.</p>
        <div className="board" style={{ marginTop: 12 }}>
          {models.loading && <Skeleton lines={3} />}
          {(models.data ?? []).map((m) => (
            <article className="req" key={m.name}>
              <header><h3 className="mono">{m.name}</h3><span className="st live">{m.version}</span></header>
              <p>{Object.entries(m.metrics).slice(0, 3).map(([k, v]) => `${k.replace(/_/g, " ")}: ${formatMetric(v)}`).join(" · ") || "No held-out metrics recorded for this model."}</p>
            </article>
          ))}
          {models.error && <Callout tone="danger" title="Could not load the registry">{models.error}</Callout>}
        </div>
      </section>

      <section aria-labelledby="audit">
        <h2 id="audit" className="section-title">{t(lang, "Audit chain")}</h2>
        {verify.loading ? <Skeleton lines={1} /> : verify.data ? (
          <Callout tone={verify.data.ok ? "ok" : "danger"} title={verify.data.ok ? "Chain intact" : "Chain BROKEN"}>
            {verify.data.entries} entries, every hash recomputed from scratch on each check. Editing or deleting any entry breaks all later hashes.
          </Callout>
        ) : <p className="note">{verify.error}</p>}
      </section>

      <div className="two-col">
        <div className="panel">
          <h2>{t(lang, "Settings")} <span className="note" style={{ fontWeight: 400 }}>({changed} changed from default)</span></h2>
          <div className="table-wrap" style={{ maxHeight: 460, overflow: "auto" }}>
            {settings.loading ? <Skeleton lines={5} /> : (
              <table className="data-table">
                <thead><tr><th>Key</th><th>Value</th><th>Status</th></tr></thead>
                <tbody>
                  {(settings.data ?? []).map((s) => (
                    <tr key={s.key}><td className="num">{s.key}</td><td className="num">{JSON.stringify(s.value)}</td><td>{s.changed && <span className="st part">changed</span>}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <div className="panel">
          <h2>{t(lang, "Recent activity")}</h2>
          <div className="body" style={{ maxHeight: 460, overflow: "auto" }}>
            {!canRead ? (
              <p className="small-note">Reading audit entries needs a lead analyst, admin or auditor role. You are signed in as {role() ?? "a visitor"}; the chain check above is open to everyone.</p>
            ) : audit.loading ? <Skeleton lines={4} /> : (audit.data?.items.length ?? 0) === 0 ? (
              <p className="small-note">No audit entries yet.</p>
            ) : (
              <ul className="reasons">
                {audit.data!.items.map((a) => (
                  <li key={a.seq}>
                    <span className="mono">#{a.seq}</span> {a.action.replace(/\./g, " · ")} on {a.target_kind}:{a.target_ref.slice(0, 18)}
                    <small>{a.actor_role} · {new Date(a.ts).toLocaleString()}</small>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
