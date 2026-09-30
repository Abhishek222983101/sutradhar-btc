// Display helpers. Money is integer satoshis everywhere; BTC and percentages are formatted only at the edge.
export const SATS_PER_BTC = 100_000_000;

export const btc = (sats: number): string => (sats / SATS_PER_BTC).toFixed(4);

export const pct = (p: number): string => `${Math.round(p * 100)}%`;

/** Two values that might round to the same whole percent (e.g. 0.999 and 0.998) — show them distinguishably. */
export function pctPair(before: number, after: number): [string, string] {
  if (Math.round(before * 100) !== Math.round(after * 100)) return [pct(before), pct(after)];
  return [`${(before * 100).toFixed(1)}%`, `${(after * 100).toFixed(1)}%`];
}

/** Microseconds since the Unix epoch (UTC) to an IST wall-clock string with an explicit offset label. */
export function ist(us: number): string {
  const d = new Date(us / 1000);
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata", year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(d);
  return `${parts} IST`;
}

/** First ten characters plus an ellipsis, for long ids in tight spaces. */
export const short = (id: string, n = 10): string => (id.length > n ? `${id.slice(0, n)}…` : id);
