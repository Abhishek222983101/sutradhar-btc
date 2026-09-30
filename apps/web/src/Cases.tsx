import { useEffect, useState } from "react";
import { api } from "./api";
import { t, type Lang } from "./i18n";

type Case = { id: string; title: string; status: string; summary: string | null };
type Item = { id: string; item_kind: string; ref: string; note: string | null };
type Note = { id: string; author_id: string; body_md: string; created_at: string };
type ExportRow = { id: string; kind: string; status: string; sha256: string | null };

const EXPORT_LABELS: Record<string, string> = {
  evidence_pack: "Evidence pack (.zip)",
  graphml: "GraphML",
  misp: "MISP event",
  i2csv: "i2 CSV",
};

export default function Cases({ runId, lang = "en" }: { runId: string; lang?: Lang }) {
  const [cases, setCases] = useState<Case[]>([]);
  const [active, setActive] = useState<Case | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [exports, setExports] = useState<ExportRow[]>([]);
  const [noteText, setNoteText] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => void api<{ items: Case[] }>("/api/v1/cases?limit=50").then((p) => setCases(p.items));
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (!active) return;
    void api<{ items: Item[] }>(`/api/v1/cases/${active.id}/items`).then((p) => setItems(p.items));
    void api<Note[]>(`/api/v1/cases/${active.id}/notes`).then(setNotes);
    setExports([]);
  }, [active]);

  const createCase = async () => {
    if (title.trim().length < 3) return;
    const c = await api<Case>("/api/v1/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
    setTitle("");
    load();
    setActive(c);
  };
  const addNote = async () => {
    if (!active || !noteText.trim()) return;
    await api(`/api/v1/cases/${active.id}/notes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body_md: noteText }) });
    setNoteText("");
    void api<Note[]>(`/api/v1/cases/${active.id}/notes`).then(setNotes);
  };
  const doExport = async (kind: string) => {
    if (!active) return;
    setBusy(kind);
    try {
      const e = await api<ExportRow>(`/api/v1/cases/${active.id}/exports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind }) });
      setExports((x) => [e, ...x]);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="wrap console">
      <div className="panel">
        <h2>{t(lang, "Cases")}</h2>
        <div className="upload">
          <div className="form-row" style={{ marginBottom: 0 }}>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t(lang, "New case title (3+ characters)")} />
          </div>
          <button className="btn" onClick={() => void createCase()}>
            {t(lang, "Create case")}
          </button>
        </div>
        <div className="leads">
          {cases.map((c) => (
            <button key={c.id} className="lead" aria-current={active?.id === c.id} onClick={() => setActive(c)}>
              <span className="t">{c.title}</span>
              <span className="m">
                <span className="st live">{c.status}</span>
              </span>
            </button>
          ))}
          {cases.length === 0 && <div className="empty">No cases yet. Start one above, or add a lead to a case from the console.</div>}
        </div>
      </div>
      <div className="detail">
        {!active ? (
          <div className="panel empty">Select a case, or create one.</div>
        ) : (
          <>
            <div className="panel">
              <h2>{active.title}</h2>
              <div className="body">
                <h3 style={{ fontSize: 16 }}>Items ({items.length})</h3>
                {items.length === 0 ? (
                  <p className="note">Nothing added yet — open a lead in the console and use "Add to case".</p>
                ) : (
                  <ul className="reasons">
                    {items.map((i) => (
                      <li key={i.id}>
                        <span className="fam">{i.item_kind}</span> {i.ref}
                        {i.note ? <small>{i.note}</small> : null}
                      </li>
                    ))}
                  </ul>
                )}
                <h3 style={{ fontSize: 16, marginTop: 16 }}>Notes</h3>
                <ul className="reasons">
                  {notes.map((n) => (
                    <li key={n.id}>
                      {n.body_md}
                      <small>{new Date(n.created_at).toLocaleString()}</small>
                    </li>
                  ))}
                  {notes.length === 0 && <li className="note">No notes yet.</li>}
                </ul>
                <div className="upload">
                  <div className="form-row" style={{ marginBottom: 0 }}>
                    <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} placeholder="Add a note for the case file…" />
                  </div>
                  <button className="btn" onClick={() => void addNote()}>
                    {t(lang, "Add note")}
                  </button>
                </div>
              </div>
            </div>
            <div className="panel">
              <h2>{t(lang, "Export evidence")}</h2>
              <div className="body">
                <div className="chips">
                  {Object.entries(EXPORT_LABELS).map(([k, label]) => (
                    <button key={k} className="chip" disabled={busy === k} onClick={() => void doExport(k)}>
                      {busy === k ? "Building…" : label}
                    </button>
                  ))}
                </div>
                {exports.length === 0 ? (
                  <p className="small-note">Every export is watermarked as synthetic data and can be checked with the Verify endpoint.</p>
                ) : (
                  <ul className="reasons">
                    {exports.map((e) => (
                      <li key={e.id}>
                        {EXPORT_LABELS[e.kind] ?? e.kind}: {e.status}
                        {e.status === "ready" && (
                          <>
                            {" — "}
                            <a href={`/api/v1/exports/${e.id}/download`} target="_blank" rel="noreferrer">
                              download
                            </a>
                          </>
                        )}
                        <small className="mono">{e.sha256?.slice(0, 16)}</small>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
