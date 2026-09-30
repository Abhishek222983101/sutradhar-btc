import { useState } from "react";
import { api } from "./api";

type Hit = { kind: string; ref: string; label: string };

// The omnibox: recognises a txid, address, IP, AS number, wallet-group id, or lead-title words.
export default function SearchBox({ runId, onOpen }: { runId: string; onOpen: (kind: string, ref: string) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const search = async (text: string) => {
    setQ(text);
    if (text.trim().length < 2) { setHits([]); return; }
    try { setHits((await api<{ hits: Hit[] }>(`/api/v1/runs/${runId}/search?q=${encodeURIComponent(text)}`)).hits); } catch { setHits([]); }
  };
  return (
    <div style={{ position: "relative" }}>
      <input value={q} onChange={(e) => void search(e.target.value)} placeholder="Search txid, address, IP, AS number, wallet group…" style={{ width: "100%", padding: 8, border: "3px solid #000", fontFamily: "inherit" }} />
      {hits.length > 0 && (
        <div style={{ position: "absolute", top: "100%", left: 0, right: 0, background: "#fff", border: "3px solid #000", zIndex: 10, maxHeight: 240, overflow: "auto" }}>
          {hits.map((h) => (
            <button key={h.kind + h.ref} className="lead" style={{ width: "100%", textAlign: "left" }} onClick={() => { onOpen(h.kind === "lead" ? "lead" : h.kind, h.ref); setHits([]); setQ(""); }}>
              <span className="t">{h.label}</span><span className="m mono">{h.kind}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
