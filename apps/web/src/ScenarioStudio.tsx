import { t, type Lang } from "./i18n";
import { CopyChip, HowTo, PageHeader } from "./ui";

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
  { name: "tiny", description: "Seconds to generate: one ransomware operation on a small economy, for tests and CI.", days: 3, users: 100, ops: ["ransomware"], ipSpace: "testnet" },
  { name: "demo", description: "The tiny world with public-looking IPs from an open GeoIP database, for the live demo.", days: 3, users: 100, ops: ["ransomware"], ipSpace: "realistic" },
  { name: "rich", description: "Ransomware, a CoinJoin coordinator and a darknet market on a busier economy, public-looking IPs.", days: 5, users: 160, ops: ["ransomware", "coinjoin", "darknet"], ipSpace: "realistic" },
  { name: "hard", description: "Rich, with more look-alike legitimate actors and slower, less regular ransomware laundering.", days: 5, users: 180, ops: ["ransomware (slow, irregular)", "coinjoin", "darknet"], ipSpace: "realistic" },
];

export default function ScenarioStudio({ lang = "en" }: { lang?: Lang } = {}) {
  return (
    <div className="wrap page">
      <PageHeader
        kicker="Requirements R-14, R-15"
        title={t(lang, "Scenario Studio")}
        lede="Every lead traces back to one of these synthetic worlds. Pick a preset, copy the command and run it offline: the same seed always gives byte-identical output. Nothing on this page calls the server."
      />
      <HowTo page="scenarios" />
      <div className="board">
        {PRESETS.map((p) => (
          <article className="req" key={p.name}>
            <header>
              <h3 className="mono">{p.name}</h3>
              <span className="st live">{p.days}d · {p.users} users</span>
            </header>
            <p>{p.description}</p>
            <p className="small-note">IP space: {p.ipSpace}{p.ops.length > 0 && <> · operations: {p.ops.join(", ")}</>}</p>
            <CopyChip value={`uv run sutradhar gen run --scenario ${p.name} --out data/${p.name}`} />
          </article>
        ))}
      </div>
      <div className="panel">
        <h2>More you can do on the command line</h2>
        <div className="body">
          <p className="note">Other output formats (csv, json, ndjson, xml), randomised worlds for training, and a realism report against stated target bands:</p>
          <CopyChip value="uv run sutradhar gen run --scenario rich --seed 1 --format xml --out worlds/rich-xml" />
          <CopyChip value="uv run sutradhar gen randomize --count 5 --seed-base 1000 --out worlds/train" />
          <CopyChip value="uv run sutradhar gen validate worlds/train/w0" />
        </div>
      </div>
    </div>
  );
}
