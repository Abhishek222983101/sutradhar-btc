import { useEffect, useState } from "react";
import { api } from "./api";
import { btc, short } from "./format";

// Object pages: actor (wallet cluster), address, transaction, IP. One component switches on `kind`.
export default function Dossier({ runId, kind, ref: reference, close }: { runId: string; kind: string; ref: string; close: () => void }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null); setError("");
    const path = kind === "actor" ? `actors/${reference}` : kind === "address" ? `addresses/${reference}` : kind === "tx" ? `tx/${reference}` : `ips/${reference}`;
    void api<Record<string, unknown>>(`/api/v1/runs/${runId}/${path}`).then(setData).catch((e) => setError((e as Error).message));
  }, [runId, kind, reference]);
  return (
    <div className="panel">
      <h2>{kind[0].toUpperCase() + kind.slice(1)}: {short(reference, 14)} <button className="chip" onClick={close} style={{ float: "right" }}>Close</button></h2>
      <div className="body">
        {error && <div className="err">{error}</div>}
        {!data && !error && <div className="note">Loading…</div>}
        {data && <pre className="mono" style={{ whiteSpace: "pre-wrap", maxHeight: 400, overflow: "auto", background: "#f7f8fb", border: "2px solid #000", padding: 10 }}>{JSON.stringify(data, null, 1)}</pre>}
      </div>
    </div>
  );
}

export function omnibox() {}
export { btc };
