import { useEffect, useId, useRef, useState } from "react";
import { api } from "./api";

type Hit = { kind: string; ref: string; label: string };
const KIND_LABEL: Record<string, string> = { lead: "lead", actor: "wallet", address: "address", tx: "transaction", ip: "IP", asn: "AS number" };

// The omnibox: recognises a txid, address, IP, AS number, wallet-group id, or lead-title words.
export default function SearchBox({ runId, onOpen }: { runId: string; onOpen: (kind: string, ref: string) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [state, setState] = useState<"idle" | "busy" | "none" | "error">("idle");
  const seq = useRef(0);
  const listId = useId();

  useEffect(() => {
    const text = q.trim();
    if (text.length < 2) { setHits([]); setState("idle"); return; }
    const mine = ++seq.current;
    setState("busy");
    const timer = window.setTimeout(async () => {
      try {
        const res = await api<{ hits: Hit[] }>(`/api/v1/runs/${runId}/search?q=${encodeURIComponent(text)}`);
        if (mine !== seq.current) return;
        setHits(res.hits); setState(res.hits.length ? "idle" : "none");
      } catch { if (mine === seq.current) { setHits([]); setState("error"); } }
    }, 220);
    return () => window.clearTimeout(timer);
  }, [q, runId]);

  const open = (h: Hit) => { onOpen(h.kind, h.ref); setHits([]); setQ(""); setState("idle"); };
  return (
    <div style={{ position: "relative" }}>
      <input
        className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search txid, address, IP, AS number, wallet group…"
        aria-label="Search the dataset" aria-controls={listId} aria-expanded={hits.length > 0} autoComplete="off" spellCheck={false}
        onKeyDown={(e) => { if (e.key === "Escape") { setHits([]); setQ(""); } if (e.key === "Enter" && hits[0]) open(hits[0]); }}
      />
      <div id={listId} role="listbox" aria-label="Search results" style={hits.length ? { position: "absolute", top: "100%", left: 0, right: 0, background: "#fff", border: "3px solid #000", zIndex: 10, maxHeight: 260, overflow: "auto" } : undefined}>
        {hits.map((h) => (
          <button key={h.kind + h.ref} role="option" aria-selected={false} className="lead" onClick={() => open(h)}>
            <span className="t">{h.label}</span><span className="m mono">{KIND_LABEL[h.kind] ?? h.kind}</span>
          </button>
        ))}
      </div>
      {state === "busy" && <p className="small-note">Searching…</p>}
      {state === "none" && <p className="small-note">Nothing matches “{q.trim()}”. Try a prefix of a txid, address or IP.</p>}
      {state === "error" && <p className="small-note">Search failed. Try again in a moment.</p>}
    </div>
  );
}
