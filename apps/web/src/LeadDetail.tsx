import { useEffect, useState } from "react";
import { api, type Evidence, type Lead, type Suggestion } from "./api";
import Canvas from "./Canvas";
import Dossier from "./Dossier";
import { EvidenceBody } from "./EvidenceViews";
import { btc, ist, pct, pctPair, short } from "./format";
import GeoBars from "./GeoBars";
import { useApi } from "./hooks";
import { t, type Lang } from "./i18n";
import Sankey from "./Sankey";
import { Callout, Empty, Skeleton, TabPanel, Tabs, type TabDef } from "./ui";

type Row = Record<string, unknown>;
type Reason = { family: string; feature: string; label?: string; value?: unknown; contribution: number; text: string };
type Explanation = {
  reasons: Reason[];
  opposing: { text: string }[];
  counterfactual: { feature: string; p_after: number; p_before: number }[];
  priority: Record<string, number>;
  provenance?: { model?: string; model_version?: string; calibrated?: boolean; drift?: { level: string; max_psi: number; shifted: string[] } };
};
type Actor = {
  cluster_id: string;
  stats: Record<string, number>;
  risk: { taint: number; hops: number; ppr: number; is_seed: boolean } | null;
  addresses: string[];
  timeline: { day: string; payments: number; sats: number }[];
  paths: { rank: number; hops: number; cost: number; path: string }[];
  partners: Row[];
  ips: { ip: string; n_tx: number; mean_p: number; country: string | null; asn: number | null; org: string | null; source: string; as_of: string }[];
};
type Page<T> = { items: T[]; next_cursor: string | null };

const FAMILY: Record<string, string> = {
  ANOM: "Anomaly: an Isolation Forest rates it as statistically rare against everything else in this data.",
  FLOW: "Value flow: the shape of how money moves in and out (peeling, sweeping, fan-out, cash-out).",
  NET: "Network origin: where the transaction was first announced (IP, timing, IPs shared between wallets).",
  TAINT: "Taint: how much of this wallet's money traces back to watchlisted seed wallets.",
  BEHAV: "Behaviour: its activity rhythm: how often it pays, how regularly, which fees, what time of day.",
};

const TAB_LABEL: Record<string, TabDef> = {
  summary: { id: "summary", label: "Summary", hint: "The score, how it was produced, and what to do next" },
  why: { id: "why", label: "Why", hint: "Each piece of evidence and how much it moved the score" },
  whatif: { id: "whatif", label: "What-if", hint: "What would change the score" },
  evidence: { id: "evidence", label: "Evidence", hint: "Link graph, transactions and propagation replay" },
  network: { id: "network", label: "Network", hint: "Origin IPs with country and ASN" },
  path: { id: "path", label: "Path to seed", hint: "How risk reaches this wallet from a seed" },
  timeline: { id: "timeline", label: "Timeline & flows", hint: "When it moved money and with whom" },
  members: { id: "members", label: "Members", hint: "Addresses in this wallet and merge suggestions" },
  tx: { id: "tx", label: "Transaction", hint: "The transaction dossier" },
};
const TABS_BY_KIND: Record<string, string[]> = {
  cluster: ["summary", "why", "whatif", "evidence", "network", "path", "timeline", "members"],
  cashout: ["summary", "why", "evidence", "network", "path"],
  ip: ["summary", "why", "evidence", "network"],
  chain: ["summary", "why"],
  tx: ["summary", "why", "tx"],
};

export const tabsFor = (kind: string): TabDef[] => (TABS_BY_KIND[kind] ?? ["summary", "why"]).map((id) => TAB_LABEL[id]);

function Problem({ message, retry }: { message: string; retry: () => void }) {
  return <Callout tone="danger" title="This part could not load">{message} <button className="chip" onClick={retry}>Try again</button></Callout>;
}

export default function LeadDetail({ lead, runId, lang, tab, onTab }: { lead: Lead; runId: string; lang: Lang; tab: string; onTab: (t: string) => void }) {
  const tabs = tabsFor(lead.subject_kind);
  const active = tabs.some((x) => x.id === tab) ? tab : "summary";
  const explain = useApi<Explanation>(`/api/v1/leads/${lead.id}/explanation`);
  const needsEvidence = ["cluster", "ip", "cashout"].includes(lead.subject_kind);
  const evidence = useApi<Evidence>(needsEvidence ? `/api/v1/leads/${lead.id}/evidence` : null);
  const actorRef = lead.subject_kind === "cluster" ? lead.subject_ref : lead.subject_kind === "cashout" ? lead.subject_ref.split("|")[0] : null;
  const actor = useApi<Actor>(actorRef ? `/api/v1/runs/${runId}/actors/${actorRef}` : null);
  const [msg, setMsg] = useState("");
  const [graph, setGraph] = useState(false);
  useEffect(() => { setMsg(""); setGraph(false); }, [lead.id]);

  const addToCase = async () => {
    try {
      const cases = await api<{ items: { id: string; title: string }[] }>("/api/v1/cases?limit=1");
      let caseId = cases.items[0]?.id;
      if (!caseId) {
        const c = await api<{ id: string }>("/api/v1/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "Working case" }) });
        caseId = c.id;
      }
      await api(`/api/v1/cases/${caseId}/items`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_kind: "lead", ref: lead.id, run_id: runId }) });
      setMsg("Added to your case. Open the Cases page to write notes and export it.");
    } catch (e) { setMsg((e as Error).message); }
  };

  return (
    <div className="panel">
      <h2>{lead.title}</h2>
      <div className="leadhead">
        <div className="score-line">
          <div><div className="big-p">{pct(lead.p)}</div><div className="note">{lead.calibrated ? "calibrated confidence" : "evidence score"}</div></div>
          <div>
            <span className={`grade ${lead.grade}`} title={gradeHelp(lead.grade)}>{lead.grade}</span> <span className="note">grade</span>
            <div style={{ marginTop: 6 }}>{lead.families.map((f) => <span className="fam" key={f} title={FAMILY[f] ?? f}>{f}</span>)}</div>
          </div>
          {lead.value_at_risk_sats > 0 && <div><b>{btc(lead.value_at_risk_sats)} BTC</b><div className="note">value involved</div></div>}
          <div className="lead-actions">
            {lead.subject_kind === "cluster" && <button className="chip" onClick={() => { setGraph((v) => !v); onTab("evidence"); }}>{graph ? "Hide" : "Investigate"} graph</button>}
            <button className="chip" onClick={() => void addToCase()}>{t(lang, "Add to case")}</button>
          </div>
        </div>
        {msg && <p className="note" role="status">{msg}</p>}
        <p className="hedge">{lead.summary}</p>
      </div>
      <Tabs tabs={tabs} value={active} onChange={onTab} label="Lead detail" />
      <TabPanel id={active}>
        {active === "summary" && <SummaryTab lead={lead} explain={explain} />}
        {active === "why" && <WhyTab explain={explain} lang={lang} />}
        {active === "whatif" && <WhatIfTab explain={explain} lang={lang} />}
        {active === "evidence" && (
          <>
            {lead.subject_kind === "cluster" && (
              <div className="form-actions">
                <button className="chip" aria-pressed={graph} onClick={() => setGraph((v) => !v)}>{graph ? "Hide" : "Investigate"} graph</button>
                <span className="note">The investigate graph is the wallet cluster with its IPs and neighbours, laid out in your browser.</span>
              </div>
            )}
            {graph && lead.subject_kind === "cluster" && <Canvas runId={runId} clusterId={lead.id} />}
            {evidence.loading ? <Skeleton lines={4} /> : evidence.error ? <Problem message={evidence.error} retry={evidence.reload} /> : evidence.data ? <EvidenceBody ev={evidence.data} /> : <Empty title="No transaction evidence" />}
          </>
        )}
        {active === "network" && <NetworkTab lead={lead} runId={runId} actor={actor} />}
        {active === "path" && <PathTab actor={actor} />}
        {active === "timeline" && <TimelineTab actor={actor} />}
        {active === "members" && <MembersTab actor={actor} runId={runId} clusterId={actorRef} />}
        {active === "tx" && <Dossier embedded runId={runId} kind="tx" ref={lead.subject_ref} />}
      </TabPanel>
    </div>
  );
}

const gradeHelp = (g: string) =>
  g === "A" ? "Grade A: at least 80% confidence and at least three independent kinds of evidence agree"
  : g === "B" ? "Grade B: at least 50% confidence and at least two independent kinds of evidence agree"
  : "Grade C: weaker or single-source evidence; worth a look, not an alarm";

function SummaryTab({ lead, explain }: { lead: Lead; explain: ReturnType<typeof useApi<Explanation>> }) {
  const e = explain.data;
  return (
    <>
      <div className="two-col">
        <div>
          <h3>How to read this lead</h3>
          <ul className="reasons">
            <li><b>Score.</b> {lead.calibrated ? "A calibrated probability: of leads scored about this high, roughly this share were real in testing." : "A transparent evidence score (not a calibrated probability): this lead type is scored by readable rules."}</li>
            <li><b>Grade {lead.grade}.</b> {gradeHelp(lead.grade).replace(/^Grade [ABC]: /, "")}.</li>
            <li><b>Families.</b> {lead.families.join(", ")}: hover a chip above for what each kind of evidence means.</li>
          </ul>
        </div>
        <div>
          <h3>Where the score came from</h3>
          {explain.loading ? <Skeleton lines={3} /> : explain.error ? <Problem message={explain.error} retry={explain.reload} /> : e && (
            <dl className="kv">
              <dt>Model</dt><dd className="mono">{e.provenance?.model_version ?? e.provenance?.model ?? lead.model_version}</dd>
              <dt>Calibrated</dt><dd>{e.provenance?.calibrated ? "yes (isotonic)" : "no (rule score)"}</dd>
              {e.provenance?.drift && <><dt>Input drift</dt><dd>{e.provenance.drift.level} (PSI {e.provenance.drift.max_psi})</dd></>}
            </dl>
          )}
        </div>
      </div>
      {e && Object.keys(e.priority).length > 0 && (
        <div>
          <h3>Why it sits where it does in the list</h3>
          <p className="mono">priority = {Object.entries(e.priority).map(([k, v]) => `${k.replace("_factor", "")} ${v}`).join(" × ")}</p>
          <p className="small-note">The list is ordered by priority, not by confidence alone: confidence × how much value is involved × how recent it is × whether there is something an investigator can act on.</p>
        </div>
      )}
    </>
  );
}

function WhyTab({ explain, lang }: { explain: ReturnType<typeof useApi<Explanation>>; lang: Lang }) {
  if (explain.loading) return <Skeleton lines={5} />;
  if (explain.error) return <Problem message={explain.error} retry={explain.reload} />;
  const e = explain.data;
  if (!e) return <Empty title="No explanation recorded" />;
  const max = Math.max(...e.reasons.map((r) => Math.abs(r.contribution)), 0.0001);
  return (
    <>
      <div>
        <h3>{t(lang, "Why this was flagged")}</h3>
        <p className="small-note" style={{ marginBottom: 10 }}>Each row is one piece of evidence. The bar is how much it contributed to the score (TreeSHAP for model-scored leads); the grey line names the evidence family and model feature.</p>
        <div style={{ display: "grid", gap: 10 }}>
          {e.reasons.map((r) => (
            <div className="contrib" key={r.feature}>
              <div className="row"><span>{r.text}</span><b className="mono">{r.contribution}</b></div>
              <div className="meter" aria-hidden="true"><i style={{ width: `${(Math.abs(r.contribution) / max) * 100}%` }} /></div>
              <small>{r.family} · {r.feature}</small>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3>{t(lang, "Against this reading")}</h3>
        {e.opposing.length === 0 ? <p className="note">Nothing in the data argues against this lead.</p> : (
          <ul className="reasons against">{e.opposing.map((o, i) => <li key={i}>{o.text}</li>)}</ul>
        )}
      </div>
    </>
  );
}

function WhatIfTab({ explain, lang }: { explain: ReturnType<typeof useApi<Explanation>>; lang: Lang }) {
  if (explain.loading) return <Skeleton lines={3} />;
  if (explain.error) return <Problem message={explain.error} retry={explain.reload} />;
  const cf = explain.data?.counterfactual ?? [];
  if (cf.length === 0) return <Empty title="No what-if for this lead">What-ifs are computed for model-scored wallet leads.</Empty>;
  return (
    <>
      <h3>{t(lang, "What would clear this")}</h3>
      <p className="small-note">Each line resets this lead's strongest evidence to a typical value and re-scores it. If the score does not move, other evidence already holds it at the ceiling, which is a finding in itself.</p>
      <ul className="reasons">
        {cf.map((c, i) => {
          if (c.p_before === c.p_after) {
            return <li key={i}>Resetting <span className="mono">{c.feature}</span> to typical on its own would not move the score. Other evidence holds it at {pct(c.p_before)}.</li>;
          }
          const [before, after] = pctPair(c.p_before, c.p_after);
          return <li key={i}>If <span className="mono">{c.feature}</span> were typical, the score would move from {before} to {after}.</li>;
        })}
      </ul>
    </>
  );
}

function NetworkTab({ lead, runId, actor }: { lead: Lead; runId: string; actor: ReturnType<typeof useApi<Actor>> }) {
  if (lead.subject_kind === "ip") return <Dossier embedded runId={runId} kind="ip" ref={lead.subject_ref} />;
  if (actor.loading) return <Skeleton lines={4} />;
  if (actor.error) return <Problem message={actor.error} retry={actor.reload} />;
  const ips = actor.data?.ips ?? [];
  if (ips.length === 0) return <Empty title="No origin IPs for this wallet">The sensors never heard its transactions first.</Empty>;
  return (
    <>
      <Callout tone="info" title="How to read this">
        Each row is an IP that the sensors heard announcing this wallet's transactions first. The percentage is the model's mean confidence that the IP is the true origin
        (a trained origin-IP model, tested on unseen worlds). Country and AS come from an offline GeoIP database, shown with its source and date.
      </Callout>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>IP</th><th>Country</th><th>AS / organisation</th><th>Tx</th><th>Confidence</th><th>Source</th></tr></thead>
          <tbody>
            {ips.map((r) => (
              <tr key={r.ip}>
                <td className="num">{r.ip}</td><td>{r.country ?? "—"}</td>
                <td>{r.asn ? `AS${r.asn}` : "—"} {r.org ?? ""}</td><td className="num">{r.n_tx}</td><td className="num">{pct(r.mean_p)}</td>
                <td className="small-note">{r.source.split(",")[0]} · {r.as_of}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div><h3>By country</h3><GeoBars origins={ips.map((r) => ({ country: r.country ?? "Unknown", p: r.mean_p }))} /></div>
    </>
  );
}

function PathTab({ actor }: { actor: ReturnType<typeof useApi<Actor>> }) {
  if (actor.loading) return <Skeleton lines={4} />;
  if (actor.error) return <Problem message={actor.error} retry={actor.reload} />;
  const a = actor.data;
  if (!a?.risk) return <Empty title="No risk propagation for this wallet">It is not reachable from any watchlist seed.</Empty>;
  const r = a.risk;
  const path = a.paths[0] ? (JSON.parse(a.paths[0].path) as string[]) : [];
  return (
    <>
      <div className="stats" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        <div className="stat"><b>{pct(r.taint)}</b><span>of its value traces to seed wallets (taint)</span></div>
        <div className="stat"><b>{r.is_seed ? "seed" : r.hops}</b><span>{r.is_seed ? "this wallet is itself on the watchlist" : "hop(s) from the nearest seed"}</span></div>
        <div className="stat"><b>{r.ppr.toFixed(3)}</b><span>personalised PageRank score</span></div>
      </div>
      {path.length > 0 ? (
        <div>
          <h3>The explaining path</h3>
          <div className="pathline" aria-label="Path from a seed wallet to this wallet">
            {path.map((id, i) => (
              <span key={id} style={{ display: "contents" }}>
                {i > 0 && <span className="arrow" aria-hidden="true">→</span>}
                <span className={`pathnode${i === 0 ? " seed" : ""}${i === path.length - 1 ? " here" : ""}`} title={id}>{short(id, 12)}{i === 0 ? " · seed" : i === path.length - 1 ? " · this wallet" : ""}</span>
              </span>
            ))}
          </div>
          <p className="small-note" style={{ marginTop: 8 }}>The path with the highest value-weighted flow ({a.paths[0].hops} hop(s), cost {a.paths[0].cost}). Lower cost means more of the money followed this route.</p>
        </div>
      ) : (
        <Callout tone="info" title={r.is_seed ? "Hop 0: this wallet is a seed" : "No path found"}>
          {r.is_seed ? "Seeds are the wallets an investigator already knows about. Risk flows outward from here to every wallet downstream." : "No chain of payments connects this wallet to a seed within the search depth; its score comes from other evidence."}
        </Callout>
      )}
      <Callout tone="ok" title="Why this is not guilt by association">
        Taint is a value-weighted haircut that decays with every hop and stops at exchanges and other services, so a customer who merely received money from an exchange is not marked.
      </Callout>
    </>
  );
}

function TimelineTab({ actor }: { actor: ReturnType<typeof useApi<Actor>> }) {
  if (actor.loading) return <Skeleton lines={4} />;
  if (actor.error) return <Problem message={actor.error} retry={actor.reload} />;
  const a = actor.data;
  if (!a) return <Empty title="No timeline" />;
  const s = a.stats;
  const maxSats = Math.max(...a.timeline.map((d) => d.sats), 1);
  return (
    <>
      <div className="stats">
        <div className="stat"><b>{s.n_addr}</b><span>addresses</span></div>
        <div className="stat"><b>{s.n_tx_sent}</b><span>payments sent</span></div>
        <div className="stat"><b>{btc(s.recv_sats)}</b><span>BTC received</span></div>
        <div className="stat"><b>{s.n_counterparties}</b><span>counterparties</span></div>
      </div>
      <p className="note">Active from {ist(s.first_us)} to {ist(s.last_us)}.</p>
      <div>
        <h3>Payments sent, by day</h3>
        <div className="tl">
          {a.timeline.map((d) => (
            <div className="r" key={d.day}>
              <span className="mono">{d.day}</span>
              <span className="bar"><i style={{ width: `${(d.sats / maxSats) * 100}%` }} /></span>
              <span className="mono">{d.payments} tx · {btc(d.sats)} BTC</span>
            </div>
          ))}
        </div>
      </div>
      {a.partners.length > 0 && (
        <div>
          <h3>Value flow with counterparties</h3>
          <p className="small-note" style={{ marginBottom: 6 }}>Green = money in, orange = money out, navy = an exchange or service. Line thickness is the amount.</p>
          <Sankey partners={a.partners} />
        </div>
      )}
    </>
  );
}

function MembersTab({ actor, runId, clusterId }: { actor: ReturnType<typeof useApi<Actor>>; runId: string; clusterId: string | null | undefined }) {
  const sug = useApi<Page<Suggestion>>(`/api/v1/runs/${runId}/suggestions?limit=100`);
  if (actor.loading) return <Skeleton lines={4} />;
  if (actor.error) return <Problem message={actor.error} retry={actor.reload} />;
  const a = actor.data;
  const mine = (sug.data?.items ?? []).filter((s) => s.a === clusterId || s.b === clusterId);
  return (
    <>
      <div>
        <h3>{a?.addresses.length ?? 0} addresses in this wallet</h3>
        <p className="small-note" style={{ marginBottom: 8 }}>Grouped by common-input ownership: these addresses were spent together in one transaction, so one party controls them. CoinJoin mixes are excluded from this rule.</p>
        <div className="members">{(a?.addresses ?? []).map((x) => <code key={x} title={x}>{short(x, 14)}</code>)}</div>
      </div>
      <div>
        <h3>Wallets that may share an operator</h3>
        {sug.loading ? <Skeleton lines={2} /> : mine.length === 0 ? (
          <p className="note">No merge suggestion involves this wallet. See the Pipeline panel below for the strongest suggestions in this run.</p>
        ) : (
          <ul className="reasons">
            {mine.map((s) => {
              const other = s.a === clusterId ? s.b : s.a;
              return <li key={s.a + s.b}><b className="mono">{short(other, 14)}</b> · score {pct(s.score)}<small>{s.reasons.join(" · ")}</small></li>;
            })}
          </ul>
        )}
        <p className="small-note" style={{ marginTop: 8 }}>Nothing merges automatically. A lead analyst accepts or rejects each suggestion and the decision is written to the audit log.</p>
      </div>
    </>
  );
}
