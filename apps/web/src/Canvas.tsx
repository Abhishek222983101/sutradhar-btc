import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { short } from "./format";

type Node = { id: string; type: string; label: string; attrs: Record<string, unknown> };
type Edge = { id: string; type: string; source: string; target: string; method: string; confidence: number; evidence_refs: Record<string, unknown> };
type Graph = { nodes: Node[]; edges: Edge[]; truncated: boolean };

const COLORS: Record<string, string> = { cluster: "#fff", service: "#ff9933", ip: "#1d2b8f" };
const EDGE_COLORS: Record<string, string> = { FLOW: "#000", ORIGINATED: "#1d2b8f", CO_ORIGIN: "#c1121f", TAINT_PATH: "#138808" };

// A simple force-directed layout (no library): Fruchterman-Reingold style repulsion + spring attraction,
// run for a fixed number of iterations client-side. Bounded to 150 nodes (the API's own cap) so this stays fast.
function layout(nodes: Node[], edges: Edge[], w: number, h: number): Map<string, { x: number; y: number }> {
  const pos = new Map(nodes.map((n, i) => [n.id, { x: w / 2 + Math.cos(i) * 100, y: h / 2 + Math.sin(i) * 100 }]));
  const k = Math.sqrt((w * h) / Math.max(1, nodes.length));
  for (let iter = 0; iter < 200; iter++) {
    const disp = new Map(nodes.map((n) => [n.id, { x: 0, y: 0 }]));
    for (const a of nodes) {
      for (const b of nodes) {
        if (a.id === b.id) continue;
        const pa = pos.get(a.id)!, pb = pos.get(b.id)!;
        const dx = pa.x - pb.x, dy = pa.y - pb.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = (k * k) / dist;
        const d = disp.get(a.id)!;
        d.x += (dx / dist) * force;
        d.y += (dy / dist) * force;
      }
    }
    for (const e of edges) {
      const pa = pos.get(e.source), pb = pos.get(e.target);
      if (!pa || !pb) continue;
      const dx = pa.x - pb.x, dy = pa.y - pb.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist * dist) / k;
      const da = disp.get(e.source)!, db = disp.get(e.target)!;
      da.x -= (dx / dist) * force; da.y -= (dy / dist) * force;
      db.x += (dx / dist) * force; db.y += (dy / dist) * force;
    }
    const temp = Math.max(1, 10 * (1 - iter / 200));
    for (const n of nodes) {
      const d = disp.get(n.id)!, p = pos.get(n.id)!;
      const len = Math.max(0.01, Math.sqrt(d.x * d.x + d.y * d.y));
      p.x = Math.min(w - 20, Math.max(20, p.x + (d.x / len) * Math.min(len, temp)));
      p.y = Math.min(h - 20, Math.max(20, p.y + (d.y / len) * Math.min(len, temp)));
    }
  }
  return pos;
}

// The investigate canvas: a bounded evidence graph around any wallet cluster, laid out client-side.
export default function Canvas({ runId, clusterId }: { runId: string; clusterId: string }) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [selected, setSelected] = useState<Node | null>(null);
  const [minConf, setMinConf] = useState(0);
  const [edgeType, setEdgeType] = useState("ALL");
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    setGraph(null);
    void api<Graph>(`/api/v1/leads/${clusterId}/subgraph`).then(setGraph).catch(() => undefined);
  }, [clusterId]);
  const filtered = useMemo(() => {
    if (!graph) return null;
    const edges = graph.edges.filter((e) => e.confidence >= minConf && (edgeType === "ALL" || e.type === edgeType));
    const keep = new Set(edges.flatMap((e) => [e.source, e.target]));
    return { nodes: graph.nodes.filter((n) => keep.has(n.id) || n.attrs.focus), edges };
  }, [graph, minConf, edgeType]);
  const pos = useMemo(() => (filtered ? layout(filtered.nodes, filtered.edges, 680, 420) : new Map()), [filtered]);
  const edgeTypes = useMemo(() => [...new Set((graph?.edges ?? []).map((e) => e.type))], [graph]);
  if (!graph) return <div className="empty">Loading graph…</div>;
  if (!filtered?.nodes.length) return <div className="empty">No graph edges meet the current filter.</div>;
  return (
    <div className="panel">
      <h2>Investigate</h2>
      <div className="body">
        <div className="chips">
          <button className="chip" aria-pressed={edgeType === "ALL"} onClick={() => setEdgeType("ALL")}>All edges</button>
          {edgeTypes.map((t) => <button key={t} className="chip" aria-pressed={edgeType === t} onClick={() => setEdgeType(t)}>{t}</button>)}
          <label className="note" style={{ marginLeft: "auto" }}>min confidence {minConf.toFixed(1)}
            <input type="range" min={0} max={1} step={0.1} value={minConf} onChange={(e) => setMinConf(Number(e.target.value))} style={{ marginLeft: 6, verticalAlign: "middle" }} />
          </label>
        </div>
        <svg ref={ref} viewBox="0 0 680 420" style={{ width: "100%", background: "#f7f8fb", border: "2px solid #000" }} role="img" aria-label="Evidence graph">
          {filtered.edges.map((e) => {
            const a = pos.get(e.source), b = pos.get(e.target);
            if (!a || !b) return null;
            return <line key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={EDGE_COLORS[e.type] ?? "#666"} strokeWidth={1 + e.confidence * 3} opacity={0.4 + e.confidence * 0.6} />;
          })}
          {filtered.nodes.map((n) => {
            const p = pos.get(n.id);
            if (!p) return null;
            const focus = Boolean(n.attrs.focus);
            return (
              <g key={n.id} onClick={() => setSelected(n)} style={{ cursor: "pointer" }}>
                <circle cx={p.x} cy={p.y} r={focus ? 12 : n.type === "ip" ? 7 : 8} fill={COLORS[n.type] ?? "#fff"} stroke="#000" strokeWidth={focus ? 4 : 2} />
                <text x={p.x} y={p.y - (focus ? 16 : 12)} textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize={10}>{n.type === "ip" ? n.label : short(n.id.replace(/^(cluster|ip):/, ""), 8)}</text>
              </g>
            );
          })}
        </svg>
        {graph.truncated && <p className="note">Graph truncated at 150 nodes.</p>}
        {selected && (
          <div className="hedge">
            <b>{selected.type}</b> · {selected.label}
            {selected.type === "ip" && <div className="mono">{JSON.stringify(selected.attrs)}</div>}
          </div>
        )}
        <p className="note">Line thickness = confidence. Orange = exchange-like service. Blue border = the wallet this graph is centred on.</p>
      </div>
    </div>
  );
}
