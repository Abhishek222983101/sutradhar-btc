import { btc, short } from "./format";

type Row = Record<string, unknown>;

const W = 560;
const H = 40;
const ROW = 34;
const PAD = 10;

// Hand-rolled two-column Sankey for one wallet's value flow: no charting library, no network fetch — every
// node position is computed from the same partner list the reasons list already renders, so the diagram never
// drifts out of sync with the evidence above it.
export default function Sankey({ partners }: { partners: Row[] }) {
  const rows = partners.slice(0, 10).map((p) => ({
    direction: p.direction as "in" | "out",
    other: p.other as string,
    is_service: Boolean(p.is_service),
    sats: Number(p.sats),
  }));
  if (rows.length === 0) return null;
  const total = rows.reduce((s, p) => s + p.sats, 0) || 1;
  const h = H + rows.length * ROW + PAD;
  const cx = W / 2;
  let y = H;

  return (
    <svg className="sankey" viewBox={`0 0 ${W} ${h}`} role="img" aria-label="Value flow, this wallet to its counterparties">
      <rect x={cx - 46} y={8} width={92} height={26} fill="var(--ink)" />
      <text x={cx} y={25} textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize="11" fill="#fff">
        this wallet
      </text>
      {rows.map((p, i) => {
        const rowY = y;
        y += ROW;
        const weight = Math.max(1.5, (p.sats / total) * 26);
        const fromX = cx + (p.direction === "out" ? 46 : -46);
        const toX = p.direction === "out" ? W - 130 : 130;
        const midY = rowY + ROW / 2 - PAD / 2;
        const color = p.is_service ? "var(--navy)" : p.direction === "out" ? "var(--saffron)" : "var(--green)";
        return (
          <g key={i}>
            <path
              className="sankey-link"
              d={`M${fromX} 30 C ${(fromX + toX) / 2} 30, ${(fromX + toX) / 2} ${midY}, ${toX} ${midY}`}
              stroke={color}
              strokeWidth={weight}
              fill="none"
              opacity={0.85}
            />
            <text
              x={p.direction === "out" ? toX + 8 : toX - 8}
              y={midY + 4}
              textAnchor={p.direction === "out" ? "start" : "end"}
              fontFamily="IBM Plex Mono, monospace"
              fontSize="11"
            >
              {short(p.other, 10)}
              {p.is_service ? " (svc)" : ""} · {btc(p.sats)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
