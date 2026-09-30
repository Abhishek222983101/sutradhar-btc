type Row = Record<string, unknown>;

// Offline stand-in for the blueprint's deck.gl geo view: no map tiles, no network request, just the country
// distribution of candidate origin IPs the engine already returned — grouped and weighted by its own confidence.
export default function GeoBars({ origins }: { origins: Row[] }) {
  const byCountry = new Map<string, number>();
  for (const o of origins) {
    const key = (o.country as string) ?? "Unknown";
    byCountry.set(key, (byCountry.get(key) ?? 0) + Number(o.p));
  }
  const rows = [...byCountry.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  const max = Math.max(...rows.map(([, v]) => v), 1);
  if (rows.length === 0) return null;

  return (
    <div className="geo-bars">
      {rows.map(([country, weight]) => (
        <div className="geo-row" key={country}>
          <span className="geo-label">{country}</span>
          <span className="geo-track">
            <span className="geo-fill" style={{ width: `${(weight / max) * 100}%` }} />
          </span>
          <span className="geo-val mono">{weight.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}
