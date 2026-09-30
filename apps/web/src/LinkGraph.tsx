import type { Evidence } from "./api";
import { short } from "./format";

// Link analysis for one lead: candidate origin IPs (left) -> transactions (middle) -> the wallet cluster (right).
// Line thickness is the model's probability that the IP first announced that transaction.
export default function LinkGraph({ ev }: { ev: Evidence }) {
  const txs = ev.transactions.slice(0, 8);
  const ips = [...new Set(txs.flatMap((t) => t.candidates.slice(0, 3).map((c) => c.ip)))].slice(0, 7);
  const H = Math.max(ips.length, txs.length) * 34 + 30;
  const yIp = (i: number) => 26 + i * ((H - 40) / Math.max(1, ips.length - 1 || 1));
  const yTx = (i: number) => 26 + i * ((H - 40) / Math.max(1, txs.length - 1 || 1));
  return (
    <svg viewBox={`0 0 760 ${H}`} role="img" aria-label="Link analysis: IPs, transactions and wallet cluster" style={{ width: "100%", background: "#f7f8fb", border: "2px solid #000" }}>
      {txs.map((t, ti) => (
        <g key={t.txid}>
          {t.candidates.slice(0, 3).map((c) => {
            const ii = ips.indexOf(c.ip);
            return ii < 0 ? null : (
              <line key={c.ip} x1={190} y1={yIp(ii)} x2={390} y2={yTx(ti)}
                stroke={c.ip === ev.ip ? "#ff9933" : "#1d2b8f"} strokeWidth={1 + c.p * 7} opacity={0.35 + c.p * 0.65} />
            );
          })}
          <line x1={470} y1={yTx(ti)} x2={600} y2={H / 2} stroke="#000" strokeWidth={2} />
          <rect x={390} y={yTx(ti) - 11} width={80} height={22} fill="#fff" stroke="#000" strokeWidth={2} />
          <text x={430} y={yTx(ti) + 4} textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize={10}>{short(t.txid, 8)}</text>
        </g>
      ))}
      {ips.map((ip, i) => (
        <g key={ip}>
          <circle cx={190} cy={yIp(i)} r={ip === ev.ip ? 9 : 6} fill={ip === ev.ip ? "#ff9933" : "#fff"} stroke="#000" strokeWidth={3} />
          <text x={176} y={yIp(i) + 4} textAnchor="end" fontFamily="IBM Plex Mono, monospace" fontSize={11} fontWeight={ip === ev.ip ? 700 : 400}>{ip}</text>
        </g>
      ))}
      <rect x={600} y={H / 2 - 24} width={140} height={48} fill="#ff9933" stroke="#000" strokeWidth={3} />
      <text x={670} y={H / 2 - 3} textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize={11}>wallet {short(ev.cluster_id, 8)}</text>
      <text x={670} y={H / 2 + 13} textAnchor="middle" fontSize={11}>{ev.addresses.length} address(es)</text>
    </svg>
  );
}
