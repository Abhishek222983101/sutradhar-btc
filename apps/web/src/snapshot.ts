// A saved copy of the hero dataset's read-only API answers (scripts/build_web_snapshot.py). While the free demo server
// wakes, the console renders from this so a visitor never meets an empty page; the app says so and swaps to live data.
type Hit = { kind: string; ref: string; label: string };
type Snap = { generated_at: string; run_id: string; paths: Record<string, unknown> };

let loading: Promise<Snap | null> | null = null;
export const loadSnapshot = (): Promise<Snap | null> => {
  loading ??= fetch("/snapshot/hero.json", { cache: "force-cache" })
    .then((r) => (r.ok ? (r.json() as Promise<Snap>) : null))
    .catch(() => null);
  return loading;
};

const lastSegment = (key: string) => decodeURIComponent(key.split("?")[0].split("/").pop() ?? "");

function search(s: Snap, raw: string): { query: string; hits: Hit[] } {
  const q = raw.trim();
  const needle = q.toLowerCase();
  const hits: Hit[] = [];
  if (q.length >= 2) {
    const asn = /^(?:AS)?(\d{1,10})$/i.exec(q);
    for (const key of Object.keys(s.paths)) {
      const id = lastSegment(key);
      if (key.includes("/ips/") && id.startsWith(q)) hits.push({ kind: "ip", ref: id, label: `IP ${id}` });
      else if (key.includes("/asn/") && asn && id === asn[1]) {
        const n = (s.paths[key] as { ips: unknown[] }).ips.length;
        hits.push({ kind: "asn", ref: id, label: `AS${id} (${n} IP(s))` });
      } else if (key.includes("/tx/") && q.length >= 6 && id.startsWith(needle)) hits.push({ kind: "tx", ref: id, label: `Transaction ${id.slice(0, 12)}…` });
      else if (key.includes("/addresses/") && q.length >= 6 && id.startsWith(q)) hits.push({ kind: "address", ref: id, label: `Address ${id.slice(0, 14)}…` });
      else if (key.includes("/actors/") && q.length >= 6 && id.startsWith(q)) hits.push({ kind: "actor", ref: id, label: `Wallet group ${id.slice(0, 10)}…` });
    }
    const leads = s.paths[`/api/v1/runs/${s.run_id}/leads?limit=100`] as { items: { id: string; title: string }[] } | undefined;
    for (const l of leads?.items ?? []) if (l.title.toLowerCase().includes(needle)) hits.push({ kind: "lead", ref: l.id, label: l.title });
  }
  const seen = new Set<string>();
  return { query: q, hits: hits.filter((h) => !seen.has(h.kind + h.ref) && seen.add(h.kind + h.ref)).slice(0, 20) };
}

/** The snapshot's answer to a GET, or undefined when it has none (the caller then waits for the live server). */
export async function snapshotGet(path: string): Promise<unknown | undefined> {
  const s = await loadSnapshot();
  if (!s) return undefined;
  const [base, qs = ""] = path.split("?");
  const params = new URLSearchParams(qs);
  if (base === `/api/v1/runs/${s.run_id}/search`) return search(s, params.get("q") ?? "");
  if (base === `/api/v1/runs/${s.run_id}/leads` && params.has("type")) {
    const all = s.paths[`${base}?limit=100`] as { items: { type: string }[] } | undefined;
    return all && { items: all.items.filter((l) => l.type === params.get("type")), next_cursor: null };
  }
  return s.paths[path];
}
