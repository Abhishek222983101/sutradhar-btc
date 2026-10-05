import { useEffect, useState } from "react";
import { api, apiBlob } from "./api";
import { t, type Lang } from "./i18n";
import { href } from "./router";
import { Callout, Empty, HowTo, PageHeader, Skeleton } from "./ui";

type Case = { id: string; title: string; status: string; summary: string | null };
type Item = { id: string; item_kind: string; ref: string; note: string | null };
type Note = { id: string; author_id: string; body_md: string; created_at: string };
type ExportRow = { id: string; kind: string; status: string; sha256: string | null; error?: string | null };

const EXPORT_LABELS: Record<string, string> = {
  evidence_pack: "Evidence pack (.zip)",
  graphml: "GraphML",
  misp: "MISP event",
  i2csv: "i2 CSV",
};
const EXPORT_HELP: Record<string, string> = {
  evidence_pack: "Sealed zip: every file hashed, manifest HMAC-sealed. Check it on the Verify page.",
  graphml: "The wallet graph for Gephi, yEd or Neo4j.",
  misp: "A MISP event for threat-intel sharing.",
  i2csv: "A flat list for i2 Analyst's Notebook.",
};
const JSON_HEADERS = { "Content-Type": "application/json" };

export default function Cases({ lang = "en" }: { runId: string; lang?: Lang }) {
  const [cases, setCases] = useState<Case[] | null>(null);
  const [active, setActive] = useState<Case | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [exports, setExports] = useState<ExportRow[]>([]);
  const [noteText, setNoteText] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = () => api<{ items: Case[] }>("/api/v1/cases?limit=50").then((p) => setCases(p.items), (e: Error) => setError(e.message));
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!active) return;
    setExports([]);
    void api<{ items: Item[] }>(`/api/v1/cases/${active.id}/items`).then((p) => setItems(p.items), () => undefined);
    void api<Note[]>(`/api/v1/cases/${active.id}/notes`).then(setNotes, () => undefined);
  }, [active]);

  const guard = async (what: string, fn: () => Promise<void>) => {
    setBusy(what); setError("");
    try { await fn(); } catch (e) { setError((e as Error).message); }
    setBusy(null);
  };
  const createCase = () => guard("create", async () => {
    if (title.trim().length < 3) throw new Error("Give the case a title of at least 3 characters.");
    const c = await api<Case>("/api/v1/cases", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ title: title.trim() }) });
    setTitle(""); await load(); setActive(c);
  });
  const addNote = () => guard("note", async () => {
    if (!active || !noteText.trim()) return;
    await api(`/api/v1/cases/${active.id}/notes`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ body_md: noteText }) });
    setNoteText("");
    setNotes(await api<Note[]>(`/api/v1/cases/${active.id}/notes`));
  });
  const doExport = (kind: string) => guard(kind, async () => {
    if (!active) return;
    const e = await api<ExportRow>(`/api/v1/cases/${active.id}/exports`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ kind }) });
    setExports((x) => [e, ...x]);
  });

  return (
    <div className="wrap page">
      <PageHeader
        kicker="Hand-off · requirement R-20"
        title={t(lang, "Cases")}
        lede="A case is the investigator's working folder: leads, notes, and four export formats to hand the findings to other tools or people."
      />
      <HowTo page="cases" />
      {error && <p className="err" role="alert">{error}</p>}
      <div className="console" style={{ padding: 0 }}>
        <aside className="sidebar"><div className="panel">
          <h2>{t(lang, "Cases")}</h2>
          <form className="upload" style={{ borderTop: 0 }} onSubmit={(e) => { e.preventDefault(); void createCase(); }}>
            <div className="form-row" style={{ marginBottom: 0 }}>
              <label htmlFor="case-title">New case title</label>
              <input id="case-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t(lang, "New case title (3+ characters)")} />
            </div>
            <button className="btn" disabled={busy === "create"}>{t(lang, "Create case")}</button>
          </form>
          <div className="leads">
            {cases === null ? <Skeleton lines={3} /> : cases.map((c) => (
              <button key={c.id} className="lead" aria-current={active?.id === c.id} onClick={() => setActive(c)}>
                <span className="t">{c.title}</span><span className="m"><span className="st live">{c.status}</span></span>
              </button>
            ))}
            {cases?.length === 0 && <Empty title="No cases yet">Create one above, or press “Add to case” on any lead in the Console.</Empty>}
          </div>
        </div></aside>

        <div className="detail">
          {!active ? <div className="panel"><Empty title="Select a case, or create one" /></div> : (
            <>
              <div className="panel">
                <h2>{active.title}</h2>
                <div className="body">
                  <div>
                    <h3>Items ({items.length})</h3>
                    {items.length === 0 ? (
                      <Callout tone="info" title="Nothing added yet">Open a lead in the <a href={href("console")}>Console</a> and press “Add to case”, then come back.</Callout>
                    ) : (
                      <ul className="reasons" style={{ marginTop: 8 }}>
                        {items.map((i) => <li key={i.id}><span className="fam">{i.item_kind}</span> <span className="mono">{i.ref}</span>{i.note ? <small>{i.note}</small> : null}</li>)}
                      </ul>
                    )}
                  </div>
                  <div>
                    <h3>Notes</h3>
                    <ul className="reasons" style={{ marginTop: 8 }}>
                      {notes.map((n) => <li key={n.id}>{n.body_md}<small>{new Date(n.created_at).toLocaleString()}</small></li>)}
                      {notes.length === 0 && <li className="note">No notes yet.</li>}
                    </ul>
                    <form style={{ marginTop: 10 }} onSubmit={(e) => { e.preventDefault(); void addNote(); }}>
                      <div className="form-row">
                        <label htmlFor="note">Add a note for the case file</label>
                        <textarea id="note" value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} placeholder="e.g. Taint path checked: 3 hops from the seed wallet, high confidence." />
                      </div>
                      <button className="btn" disabled={busy === "note" || !noteText.trim()}>{t(lang, "Add note")}</button>
                    </form>
                  </div>
                </div>
              </div>
              <div className="panel">
                <h2>{t(lang, "Export evidence")}</h2>
                <div className="body">
                  <div className="board" style={{ margin: 0, gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))" }}>
                    {Object.entries(EXPORT_LABELS).map(([k, label]) => (
                      <div className="req" key={k}>
                        <h3>{label}</h3>
                        <p>{EXPORT_HELP[k]}</p>
                        <button className="chip" style={{ justifySelf: "start" }} disabled={busy === k} onClick={() => void doExport(k)}>{busy === k ? "Building…" : "Export"}</button>
                      </div>
                    ))}
                  </div>
                  {exports.length > 0 && (
                    <ul className="reasons">
                      {exports.map((e) => (
                        <li key={e.id}>
                          {EXPORT_LABELS[e.kind] ?? e.kind}: <b>{e.status}</b>
                          {e.status === "ready" && <> — <ExportDownload id={e.id} kind={e.kind} /></>}
                          {e.error && <small>{e.error}</small>}
                          {e.sha256 && <small className="mono">sha256 {e.sha256.slice(0, 32)}…</small>}
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="small-note">Every export is audit-logged and watermarked as synthetic data. Evidence packs can be checked on the <a href={href("verify")}>Verify page</a>.</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/** The download needs the signed-in session, so it is fetched with credentials rather than linked directly. */
function ExportDownload({ id, kind }: { id: string; kind: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const ext = { evidence_pack: "zip", graphml: "graphml", misp: "json", i2csv: "csv" }[kind] ?? "bin";
  const go = async () => {
    setBusy(true); setErr("");
    try {
      const url = URL.createObjectURL(await apiBlob(`/api/v1/exports/${id}/download`));
      const a = document.createElement("a");
      a.href = url; a.download = `${kind}-${id}.${ext}`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  };
  return <><button className="chip" onClick={() => void go()} disabled={busy}>{busy ? "Preparing…" : "download"}</button>{err && <small className="err">{err}</small>}</>;
}
