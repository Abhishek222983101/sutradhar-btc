import { t, type Lang } from "./i18n";

// Read-only view onto the generator's own scenario presets (packages/generator/sutradhar_gen/config.py PRESETS).
// The blueprint's own scope-cut order keeps generation on the CLI and drops the UI that would trigger it live —
// running a multi-day world generation from a public demo backend is a resource-exhaustion risk we don't take.
// This page is the informational half of that trade: browse what each preset builds and the exact command to
// run it yourself, offline, with no server-side execution surface added.
type Preset = {
  name: string;
  description: string;
  days: number;
  users: number;
  ops: string[];
  ipSpace: "testnet" | "realistic";
};

const PRESETS: Preset[] = [
  { name: "tiny", description: "Seconds to generate: one of everything, for tests and CI.", days: 1, users: 40, ops: [], ipSpace: "testnet" },
  { name: "demo", description: "The tiny world with public-looking IPs from an open GeoIP database, for the live demo.", days: 1, users: 40, ops: [], ipSpace: "realistic" },
  { name: "rich", description: "Ransomware, a CoinJoin coordinator and a darknet market on a busier economy, public-looking IPs.", days: 5, users: 160, ops: ["ransomware", "coinjoin", "darknet"], ipSpace: "realistic" },
  { name: "hard", description: "Rich, with more look-alike legitimate actors and slower, less regular ransomware laundering.", days: 5, users: 180, ops: ["ransomware (slow, irregular)", "coinjoin", "darknet"], ipSpace: "realistic" },
];

export default function ScenarioStudio({ lang = "en" }: { lang?: Lang } = {}) {
  return (
    <div className="wrap">
      <section style={{ paddingTop: 32 }}>
        <h2 className="section-title">{t(lang, "Scenario Studio")}</h2>
        <p className="note">
          Every published lead traces back to one of these synthetic worlds. Pick a preset, copy the command, run it
          offline — nothing here calls the server.
        </p>
      </section>
      <div className="board" style={{ marginTop: 20 }}>
        {PRESETS.map((p) => (
          <article className="req" key={p.name}>
            <header>
              <h3 className="mono">{p.name}</h3>
              <span className="st live">{p.days}d · {p.users} users</span>
            </header>
            <p>{p.description}</p>
            <p className="small-note">
              IP space: {p.ipSpace}
              {p.ops.length > 0 && <> · ops: {p.ops.join(", ")}</>}
            </p>
            <pre className="mono" style={{ background: "#f1f3f6", border: "2px solid var(--ink)", padding: "8px 10px", fontSize: 13, overflowX: "auto" }}>
              uv run sutradhar gen run --scenario {p.name} --out data/{p.name}
            </pre>
          </article>
        ))}
      </div>
    </div>
  );
}
