import { useEffect, useMemo, useRef, useState } from "react";
import type { Evidence } from "./api";
import { btc, pct } from "./format";
import LinkGraph from "./LinkGraph";

type Tx = Evidence["transactions"][number];

export function EvidenceBody({ ev }: { ev: Evidence }) {
  return (
    <>
      <p className="note">
        {ev.addresses.length} address(es) in this wallet, grouped because they were spent together. Thicker lines in the graph mean the IP is more
        likely the first sender. Below, each transaction lists its most likely origin IPs; press Replay to watch the first announcements arrive.
      </p>
      <LinkGraph ev={ev} />
      {ev.transactions.map((t) => <TxCard key={t.txid} tx={t} target={ev.ip ?? ""} />)}
    </>
  );
}

function TxCard({ tx, target }: { tx: Tx; target: string }) {
  return (
    <div className="tx">
      <div className="mono">tx {tx.txid.slice(0, 16)}… · {btc(tx.sats)} BTC</div>
      <div>
        {tx.candidates.slice(0, 3).map((c) => (
          <div className="cand" key={c.ip}>
            <span className="mono" style={c.ip === target ? { fontWeight: 700 } : undefined}>{c.ip}</span>
            <span className="bar"><i style={{ width: pct(c.p) }} /></span><b>{pct(c.p)}</b>
          </div>
        ))}
      </div>
      <Replay arrivals={tx.arrivals} target={target} />
    </div>
  );
}

// Replays the first announcements of a transaction as sensors heard them. Positions are a stable hash, timing is real.
function Replay({ arrivals, target }: { arrivals: Tx["arrivals"]; target: string }) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const last = Math.max(1, ...arrivals.map((a) => a.dt_ms));
  const raf = useRef(0);
  const reduced = useMemo(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches, []);
  useEffect(() => {
    if (!playing) return;
    const start = performance.now() - (t >= last ? 0 : (t / last) * 2500);
    const tick = (now: number) => {
      const f = Math.min(1, (now - start) / 2500);
      setT(f * last);
      if (f < 1) raf.current = requestAnimationFrame(tick); else setPlaying(false);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);
  const shown = reduced ? last : t;
  const pos = (s: string, salt: number) => { let h = salt; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 997; return 6 + (h / 997) * 88; };
  return (
    <div className="replay">
      <div className="stage" role="img" aria-label="Replay of the first announcements of this transaction">
        {arrivals.map((a, i) => (
          <span key={i} className={`dot${a.from === target ? " first" : ""}${a.dt_ms > shown ? " hidden" : ""}`}
            title={`${a.from} → ${a.sensor} at +${a.dt_ms} ms`} style={{ left: `${pos(a.from, 7)}%`, top: `${pos(a.sensor + a.from, 13)}%` }} />
        ))}
      </div>
      <div className="axis">
        <button className="chip" onClick={() => { setT(0); setPlaying(true); }} disabled={reduced}>Replay</button>
        <span className="mono">+{Math.round(shown)} ms of {Math.round(last)} ms · orange = the suspected origin</span>
      </div>
    </div>
  );
}
