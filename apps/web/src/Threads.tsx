// The hero picture: IP addresses on the left, wallets on the right, threads showing which IP sits behind which wallet.
const IPS = [30, 78, 126, 174, 222, 270].map((y, i) => ({ y, label: ["198.51.100.102", "192.0.2.42", "203.0.113.118", "192.0.2.4", "198.51.100.175", "192.0.2.41"][i] }));
const WALLETS = [50, 130, 210, 290];
const LINKS: [number, number, boolean][] = [[0, 0, true], [1, 0, false], [2, 1, false], [3, 1, false], [4, 2, true], [5, 3, false], [1, 3, false], [3, 2, false]];

export default function Threads() {
  return (
    <div className="threads" aria-hidden="true">
      <svg viewBox="0 0 520 320" role="img">
        {LINKS.map(([a, b, hot], i) => (
          <path key={i} className={`thread${hot ? " hot" : ""}`} d={`M120 ${IPS[a].y} C 250 ${IPS[a].y}, 270 ${WALLETS[b]}, 400 ${WALLETS[b]}`} style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
        {IPS.map((ip) => (
          <g key={ip.label}>
            <circle cx="120" cy={ip.y} r="8" fill="#fff" stroke="#000" strokeWidth="3" />
            <text x="106" y={ip.y + 4} textAnchor="end" fontFamily="IBM Plex Mono, monospace" fontSize="11">{ip.label}</text>
          </g>
        ))}
        {WALLETS.map((y, i) => (
          <g key={y}>
            <rect x="400" y={y - 18} width="90" height="36" fill={i === 0 || i === 2 ? "#ff9933" : "#fff"} stroke="#000" strokeWidth="3" />
            <text x="445" y={y + 4} textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize="11">bc1q…{["9k2f", "x7ma", "p03d", "w81c"][i]}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
