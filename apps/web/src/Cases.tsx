import { useEffect, useState } from "react";
import { api } from "./api";

type Case = { id: string; title: string; status: string; summary: string | null };
type Item = { id: string; item_kind: string; ref: string; note: string | null };
type Note = { id: string; author_id: string; body_md: string; created_at: string };
type ExportRow = { id: string; kind: string; status: string; sha256: string | null };

export default function Cases({ runId }: { runId: string }) {
  const [cases, setCases] = useState<Case[]>([]);
  const [active, setActive] = useState<Case | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [exports, setExports] = useState<ExportRow[]>([]);
  const [noteText, setNoteText] = useState("");
  const [title, setTitle] = useState("");

  const load = () => void api<{ items: Case[] }>("/api/v1/cases?limit=50").then((p) => setCases(p.items));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!active) return;
    void api<{ items: Item[] }>(`/api/v1/cases/${active.id}/items`).then((p) => setItems(p.items));
    void api<Note[]>(`/api/v1/cases/${active.id}/notes`).then(setNotes);
  }, [active]);

  const createCase = async () => {
    if (title.trim().length < 3) return;
    const c = await api<Case>("/api/v1/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
    setTitle(""); load(); setActive(c);
  };
  const addNote = async () => {
    if (!active || !noteText.trim()) return;
    await api(`/api/v1/cases/${active.id}/notes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body_md: noteText }) });
    setNoteText("");
    void api<Note[]>(`/api/v1/cases/${active.id}/notes`).then(setNotes);
  };
  const doExport = async (kind: string) => {
    if (!active) return;
    const e = await api<ExportRow>(`/api/v1/cases/${active.id}/exports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind }) });
    setExports((x) => [e, ...x]);
  };

  return (
    <div className="console">
      <div className="panel">
        <h2>Cases</h2>
        <div className="upload">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New case title" style={{ padding: 8, border: "3px solid #000" }} />
          <button className="btn" onClick={() => void createCase()}>Create case</button>
        </div>
        <div className="leads">
          {cases.map((c) => (
            <button key={c.id} className="lead" aria-current={active?.id === c.id} onClick={() => setActive(c)}>
              <span className="t">{c.title}</span><span className="m"><span className="st live">{c.status}</span></span>
            </button>
          ))}
          {cases.length === 0 && <div className="empty">No cases yet.</div>}
        </div>
      </div>
      <div className="detail">
        {!active ? <div className="panel empty">Select or create a case.</div> : (
          <>
            <div className="panel">
              <h2>{active.title}</h2>
              <div className="body">
                <h3 style={{ fontSize: 16 }}>Items ({items.length})</h3>
                {items.length === 0 ? <p className="note">Add leads or actors from the console (button coming from the lead panel).</p> : (
                  <ul className="reasons">{items.map((i) => <li key={i.id}><b>{i.item_kind}</b>: {i.ref}{i.note ? ` — ${i.note}` : ""}</li>)}</ul>
                )}
                <h3 style={{ fontSize: 16 }}>Notes</h3>
                <ul className="reasons">{notes.map((n) => <li key={n.id}>{n.body_md}<small>{new Date(n.created_at).toLocaleString()}</small></li>)}</ul>
                <div className="upload">
                  <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} style={{ padding: 8, border: "3px solid #000", fontFamily: "inherit" }} />
                  <button className="btn" onClick={() => void addNote()}>Add note</button>
                </div>
              </div>
            </div>
            <div className="panel">
              <h2>Export evidence</h2>
              <div className="body">
                <div className="chips">
                  {["evidence_pack", "graphml", "misp", "i2csv"].map((k) => <button key={k} className="chip" onClick={() => void doExport(k)}>{k}</button>)}
                </div>
                <ul className="reasons">
                  {exports.map((e) => (
                    <li key={e.id}>{e.kind}: {e.status}{e.status === "ready" && <> — <a href={`/api/v1/exports/${e.id}/download`} target="_blank" rel="noreferrer">download</a></>}
                      <small className="mono">{e.sha256?.slice(0, 16)}</small></li>
                  ))}
                </ul>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
