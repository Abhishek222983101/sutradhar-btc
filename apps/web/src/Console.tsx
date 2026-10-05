import { useCallback, useEffect, useState } from "react";
import { api, type Lead } from "./api";
import DataPanel from "./DataPanel";
import Dossier from "./Dossier";
import { pct } from "./format";
import { t, type Lang } from "./i18n";
import LeadDetail, { tabsFor } from "./LeadDetail";
import PipelinePanel from "./PipelinePanel";
import { setParam, type Route } from "./router";
import SearchBox from "./SearchBox";
import Upload from "./Upload";
import { Empty, HowTo, Skeleton } from "./ui";

const TYPES = ["ALL", "ACTOR", "CASHOUT", "IP", "CHAIN", "TX"] as const;
type LeadType = (typeof TYPES)[number];
const NAMES: Record<LeadType, string> = { ALL: "All", ACTOR: "Wallet", CASHOUT: "Cash-out", IP: "IP", CHAIN: "Peel chain", TX: "Unusual tx" };

type Page<T> = { items: T[]; next_cursor: string | null };

/** The ref a deep link can name: a short, stable prefix of the lead's subject. */
const refKey = (l: Lead) => l.subject_ref.split("|")[0].slice(0, 14);
const matches = (l: Lead, q: string) => {
  const needle = q.toLowerCase();
  return l.subject_ref.toLowerCase().startsWith(needle) || l.subject_ref.toLowerCase().includes(needle) || l.title.toLowerCase().includes(needle);
};

export default function Console({ route, lang = "en" }: { route: Route; lang?: Lang }) {
  const p = route.params;
  const filter: LeadType = (TYPES as readonly string[]).includes(p.filter ?? "") ? (p.filter as LeadType) : "ALL";
  const [leads, setLeads] = useState<Lead[]>([]);
  const [sel, setSel] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [datasetId, setDatasetId] = useState("ds_hero");
  const [runId, setRunId] = useState("run_hero");
  const [dossier, setDossier] = useState<{ kind: string; ref: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const q = filter === "ALL" ? "" : `&type=${filter}`;
      const page = await api<Page<Lead>>(`/api/v1/runs/${runId}/leads?limit=100${q}`);
      setLeads(page.items);
    } catch (e) { setError((e as Error).message); }
    setLoading(false);
  }, [filter, runId]);
  useEffect(() => { void load(); }, [load]);

  // Selection follows the address bar: ?lead=<ref prefix> picks a lead, ?open=kind:ref opens a dossier.
  useEffect(() => {
    if (p.open) {
      const [kind, ...rest] = p.open.split(":");
      if (rest.length) { setDossier({ kind, ref: rest.join(":") }); return; }
    }
    setDossier(null);
    if (!leads.length) { setSel(null); return; }
    const wanted = p.lead ? leads.find((l) => matches(l, p.lead)) : undefined;
    setSel((cur) => wanted ?? leads.find((l) => l.id === cur?.id) ?? leads[0]);
  }, [leads, p.lead, p.open]);

  useEffect(() => {
    if (!p.section || loading) return;
    document.getElementById(`section-${p.section}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [p.section, loading]);

  const pick = (l: Lead) => { setSel(l); setDossier(null); setParam("open", null); setParam("lead", refKey(l)); };
  const tab = p.tab ?? "summary";

  return (
    <div className="wrap page" style={{ paddingBlockStart: 20 }}>
      <HowTo page="console" />
      <div className="console" style={{ padding: 0 }}>
        <aside className="sidebar" aria-label="Leads">
          <div className="panel">
            <h2>{t(lang, "Leads, most urgent first")}</h2>
            <div style={{ padding: "10px 14px" }}>
              <SearchBox
                runId={runId}
                onOpen={(kind, ref) => {
                  if (kind === "lead") { const found = leads.find((l) => l.id === ref); if (found) pick(found); }
                  else { setDossier({ kind, ref }); setParam("open", `${kind}:${ref}`); }
                }}
              />
            </div>
            <div className="chips" role="group" aria-label="Filter by lead type">
              {TYPES.map((x) => (
                <button key={x} className="chip" aria-pressed={filter === x} onClick={() => setParam("filter", x === "ALL" ? null : x)}>{NAMES[x]}</button>
              ))}
            </div>
            <div className="leads">
              {loading && <Skeleton lines={6} />}
              {error && <div className="err" style={{ margin: 12 }}>{error} <button className="chip" onClick={() => void load()}>Try again</button></div>}
              {!loading && !leads.length && !error && <Empty title="No leads of this type" />}
              {leads.map((l) => (
                <button key={l.id} className="lead" aria-current={sel?.id === l.id && !dossier} onClick={() => pick(l)}>
                  <span className="t">{l.title}</span>
                  <span className="m">
                    <span className={`grade ${l.grade}`} title={`Grade ${l.grade}`}>{l.grade}</span>
                    <span className="bar" aria-hidden="true"><i style={{ width: pct(l.p) }} /></span>
                    <b>{pct(l.p)}</b>
                  </span>
                </button>
              ))}
            </div>
            <Upload onDone={(d, r) => { setDatasetId(d); setRunId(r); setParam("lead", null); }} />
          </div>
        </aside>
        <div className="detail">
          {dossier ? (
            <Dossier
              key={`${dossier.kind}:${dossier.ref}`}
              runId={runId} kind={dossier.kind} ref={dossier.ref}
              close={() => { setDossier(null); setParam("open", null); }}
              onOpen={(kind, ref) => { setDossier({ kind, ref }); setParam("open", `${kind}:${ref}`); }}
            />
          ) : sel ? (
            <LeadDetail key={sel.id} lead={sel} runId={runId} lang={lang} tab={tab} onTab={(x) => setParam("tab", tabsFor(sel.subject_kind)[0].id === x ? null : x)} />
          ) : loading ? (
            <div className="panel"><Skeleton lines={8} /></div>
          ) : (
            <div className="panel"><Empty title="Select a lead, or search above" /></div>
          )}
          <PipelinePanel runId={runId} />
          <div id="section-xray"><DataPanel datasetId={datasetId} /></div>
        </div>
      </div>
    </div>
  );
}
