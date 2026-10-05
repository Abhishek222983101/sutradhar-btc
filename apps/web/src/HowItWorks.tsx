import { useEffect, useState } from "react";
import { publicGet, type Eval } from "./api";
import { useApi } from "./hooks";
import { href } from "./router";
import { Callout, PageHeader, Skeleton } from "./ui";

const REPO = "https://github.com/Abhishek222983101/sutradhar-btc";
const DOC = (n: string) => `${REPO}/blob/main/docs/${n}`;

type Model = { name: string; version: string; status?: string; metrics: Record<string, number>; trained_on: Record<string, unknown> };

const STAGES: [string, string, string][] = [
  ["E01", "Load", "Freeze the run's view of the dataset and its capability profile."],
  ["E02", "GeoIP enrichment", "Country and ASN for every IP from the bundled DB-IP Lite, tagged with source and date."],
  ["E03", "Value flows", "Money moving between wallet clusters."],
  ["E04", "CoinJoin detection", "Trained classifier over structural features; keeps mixes out of clustering."],
  ["E05", "Wallet clustering", "Common-input ownership with a CoinJoin guard (invariant I8)."],
  ["E06", "Change-address model", "Which output of a small payment is the sender's own change."],
  ["E07", "Peel chains", "Timing-aware traversal of spend, pay a little, send the rest onward."],
  ["E08", "Anomaly model", "Isolation Forest over transaction shape: how statistically unusual is it?"],
  ["E09", "Origin IP model", "Which IP first put each transaction on the network, with probabilities."],
  ["E11", "Co-origin linking", "Wallets whose transactions keep being first heard from the same IP."],
  ["E12", "Graph embeddings", "16-dimension vector per wallet from the flow graph (truncated SVD)."],
  ["E13", "Risk propagation", "Haircut taint from watchlist seeds, with hop decay and service stopping."],
  ["E14", "Behaviour fingerprints", "A standardised vector describing how a wallet behaves."],
  ["E15", "Motifs", "Recurring transaction shapes: consolidation, fan-out."],
  ["E16", "Merge suggestions", "Wallet pairs that may share an operator, with reasons."],
  ["E17", "Lead ranking", "Calibrated, graded, prioritised leads of five types."],
  ["E18", "Explanations", "Reasons, opposing evidence, counterfactuals, drift, hedged summary."],
  ["E19", "Publish", "Validate invariants, compute digests, write the manifest."],
  ["E20", "Services and victims", "Separate exchanges and batch payers from individual actors."],
  ["E21", "Risk paths", "Personalised PageRank, k-best paths, cash-out detection."],
  ["E22", "Actor features", "About 36 features per active wallet for the ranker."],
];

const MODEL_INFO: Record<string, { what: string; why: string; baseline: string }> = {
  lead_ranker: { what: "Ranks wallet clusters by how likely they are illicit, from ~36 features.", why: "Gradient-boosted trees handle mixed, skewed features well, give exact TreeSHAP explanations, and isotonic calibration makes the score a real probability.", baseline: "Taint alone (PR-AUC 0.963 with seeds, 0.013 without)." },
  origin: { what: "Which IP first put a transaction on the network.", why: "A small logistic model on timing features is transparent, fast and hard to overfit; it is evaluated on worlds it has never seen.", baseline: "Earliest announcer wins, and random guessing among announcers." },
  change: { what: "Which output of a payment is the sender's change.", why: "Logistic regression on output shape; only links above a strict confidence are used for clustering, because looser links lowered purity.", baseline: "Measured against hidden truth: share of change outputs identified, and precision of the links used for clustering (docs/EVAL.md)." },
  coinjoin: { what: "Whether a transaction is a collaborative equal-output mix.", why: "A trained classifier over 12 structural features replaced a scored rule, so mixing detection is a model with held-out metrics, not a threshold.", baseline: "The scored heuristic it replaced (kept as the fallback and as the evaluation baseline)." },
};
const modelInfo = (name: string) => MODEL_INFO[Object.keys(MODEL_INFO).find((k) => name.startsWith(k)) ?? ""];

const FIELDS: [string, string][] = [
  ["timestamp", "UTC, microsecond precision, ISO-8601"],
  ["src_ip, src_port, dst_ip, dst_port", "who announced to whom; the network layer"],
  ["txid", "64-hex transaction id"],
  ["input_addresses[], output_addresses[]", "wallets on each side"],
  ["input_amounts[], output_amounts[]", "exact: parsed as decimals and stored as integer satoshis, never floats"],
  ["fee", "computed from inputs minus outputs when absent"],
  ["script_type", "inferred from the address format when absent"],
  ["geo_country, asn", "optional; otherwise filled from the offline GeoIP database"],
];

function Architecture() {
  const box = (x: number, y: number, w: number, h: number, fill = "#fff") => (
    <g>
      <rect x={x + 4} y={y + 4} width={w} height={h} fill="#0b0d12" />
      <rect x={x} y={y} width={w} height={h} fill={fill} stroke="#0b0d12" strokeWidth="3" />
    </g>
  );
  const head = (x: number, y: number, w: number, label: string, fill: string) => (
    <g><rect x={x} y={y} width={w} height="30" fill={fill} stroke="#0b0d12" strokeWidth="3" /><text x={x + 12} y={y + 21} fontSize="14" fontWeight="800">{label}</text></g>
  );
  const lines = (x: number, y: number, items: string[], size = 12.5, gap = 22) => items.map((t, i) => <text key={t} x={x} y={y + i * gap} fontSize={size}>{t}</text>);
  const arrow = (x1: number, x2: number, y: number) => <path d={`M${x1} ${y} H${x2 - 6}`} stroke="#0b0d12" strokeWidth="3" markerEnd="url(#head)" fill="none" />;
  return (
    <svg className="arch" viewBox="0 0 1000 440" role="img" aria-labelledby="arch-t arch-d">
      <title id="arch-t">Sutradhar architecture</title>
      <desc id="arch-d">Data sources flow through ingestion into a 21-stage analysis engine, which produces ranked leads with evidence, served by an API to the web console. Everything sits inside an offline boundary.</desc>
      <defs><marker id="head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#0b0d12" /></marker></defs>
      <rect x="8" y="30" width="984" height="402" fill="none" stroke="#0b0d12" strokeWidth="2.5" strokeDasharray="9 7" />
      <text x="22" y="22" fontSize="13" fontWeight="800" className="mono-t">OFFLINE BOUNDARY · the application opens no outbound socket (invariant I1)</text>

      {box(28, 76, 150, 300)}{head(28, 76, 150, "1 · Sources", "#ffe3c2")}
      {lines(40, 128, ["Traffic file:", "CSV · JSON", "NDJSON · XML", "", "Watchlist seeds", "(wallets, IPs)", "", "GeoIP database", "(bundled, DB-IP)"], 12.5, 22)}

      {arrow(182, 212, 226)}
      {box(214, 76, 150, 300)}{head(214, 76, 150, "2 · Ingest", "#dfe3ff")}
      {lines(226, 128, ["Streaming readers", "Mapping + auto-map", "Exact satoshis", "XML attack-safe", "Validate → rejects", "Dataset X-ray", "", "Capability profile", "switches stages"], 12.5, 22)}

      {arrow(368, 398, 226)}
      {box(400, 76, 300, 300)}{head(400, 76, 300, "3 · Engine · 21 stages", "#ffe3c2")}
      {[
        ["Chain", "flows · CoinJoin · clusters · change · peel", "#fff"],
        ["Network", "origin IP model · co-origin linking", "#fff"],
        ["Risk", "taint · PageRank · services · victims", "#fff"],
        ["ML", "Isolation Forest · features · LightGBM ranker", "#dfe3ff"],
        ["Explain", "TreeSHAP · counterfactual · publish", "#dfe3ff"],
      ].map(([a, b, f], i) => (
        <g key={a}>
          <rect x="414" y={118 + i * 50} width="272" height="42" fill={f} stroke="#0b0d12" strokeWidth="2" />
          <text x="424" y={136 + i * 50} fontSize="13" fontWeight="800">{a}</text>
          <text x="424" y={152 + i * 50} fontSize="11.5">{b}</text>
        </g>
      ))}

      {arrow(704, 734, 226)}
      {box(736, 76, 110, 300)}{head(736, 76, 110, "4 · Leads", "#ffe3c2")}
      {lines(746, 128, ["Ranked,", "graded,", "calibrated", "", "Reasons", "Against", "What-if", "", "Evidence", "envelope"], 12.5, 22)}

      {arrow(850, 878, 226)}
      {box(880, 76, 100, 300)}{head(880, 76, 100, "5 · Serve", "#dfe3ff")}
      {lines(890, 128, ["API", "auth · RBAC", "audit chain", "", "Console", "(this site)", "", "Sealed", "exports"], 12, 22)}

      <text x="28" y="412" fontSize="12.5">Every stage writes tables and a digest. The same input always gives the same result digest, so every number on this site is reproducible.</text>
    </svg>
  );
}

export default function HowItWorks() {
  const models = useApi<Model[]>("/api/v1/models");
  const [ev, setEv] = useState<Eval | null>(null);
  useEffect(() => { publicGet<Eval>("/api/v1/eval").then(setEv, () => undefined); }, []);
  const pc = (v: number) => `${Math.round(v * 1000) / 10}%`;

  return (
    <div className="wrap page">
      <PageHeader
        kicker="Requirements R-07 and R-19"
        title="How it works"
        lede="The approach, the models and why each was chosen, how explanations are produced, and where we are candid about limits. Everything on this page is read from the running system or the repository."
      />
      <nav className="toc" aria-label="Contents">
        {[["arch", "Architecture"], ["pipeline", "Pipeline"], ["models", "Models"], ["explain", "Explainability"], ["data", "Data contract"], ["eval", "Evaluation"], ["trust", "Security"], ["limits", "Limits"]].map(([id, l]) => <a key={id} href={`#${id}`} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}>{l}</a>)}
      </nav>

      <section id="arch" aria-labelledby="h-arch">
        <h2 id="h-arch" className="section-title">The system in one picture</h2>
        <p className="section-sub" style={{ marginBottom: 12 }}>Traffic and blockchain data go in; ranked, explained, evidence-backed leads come out; and nothing needs the internet.</p>
        <Architecture />
      </section>

      <section id="pipeline" aria-labelledby="h-pipe">
        <h2 id="h-pipe" className="section-title">The pipeline: 21 stages</h2>
        <p className="section-sub" style={{ marginBottom: 12 }}>Stages run in a fixed order and are skipped when the data lacks what they need (a file with no IPs runs the chain stages only). Open any lead's Console page to see the counts each stage produced.</p>
        <div className="stage-grid">
          {STAGES.map(([c, n, d]) => <div className="stage-card" key={c}><span className="code">{c}</span><b>{n}</b><span>{d}</span></div>)}
        </div>
      </section>

      <section id="models" aria-labelledby="h-models">
        <h2 id="h-models" className="section-title">The models, and why these</h2>
        <p className="section-sub" style={{ marginBottom: 12 }}>The problem statement asks for a working model, not just rules. These are trained models with published metrics against rule baselines, read live from the model registry. Every one is trained on generated worlds with hidden ground truth and tested on worlds it never saw.</p>
        {models.loading ? <Skeleton lines={4} /> : models.error ? <Callout tone="warn" title="The live registry did not load">{models.error}. The list below is on the Govern page once the server responds.</Callout> : (
          <div className="stage-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))" }}>
            {(models.data ?? []).map((m) => {
              const info = modelInfo(m.name);
              return (
                <article className="model-card" key={m.name}>
                  <header><b className="mono">{m.name}</b><span className="st live">{m.version}</span></header>
                  <div className="m-body">
                    {info && <><p><b>Does:</b> {info.what}</p><p><b>Why this model:</b> {info.why}</p><p><b>Beats:</b> {info.baseline}</p></>}
                    <div className="chipline">
                      {Object.entries(m.metrics).slice(0, 4).map(([k, v]) => <span className="metric" key={k}>{k.replace(/_/g, " ")}: {Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3)}</span>)}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
        <p className="small-note" style={{ marginTop: 10 }}>Also trained or fitted, outside the registry: the Isolation Forest anomaly model (unsupervised) and the 16-dimension graph embeddings. See <a href={href("govern")}>Govern</a> for settings and the audit trail.</p>
      </section>

      <section id="explain" aria-labelledby="h-exp">
        <h2 id="h-exp" className="section-title">How explanations are produced</h2>
        <div className="three-col" style={{ marginTop: 12 }}>
          <div className="panel"><h2>1 · Contributions</h2><div className="body"><p>The ranker's score is split into one contribution per feature with TreeSHAP, which is exact for tree models. The strongest become the "Why" bars.</p></div></div>
          <div className="panel"><h2>2 · Plain language</h2><div className="body"><p>Each contribution is rendered through a template. A language guard (tested) forbids wording that states identity or guilt: every lead says "a lead for review, not a finding about anyone".</p></div></div>
          <div className="panel"><h2>3 · Counter-evidence and what-if</h2><div className="body"><p>The system also lists evidence that argues against the lead, and re-scores the wallet with its strongest evidence reset to typical to show what would clear it.</p></div></div>
        </div>
        <Callout tone="ok" title="Confidence you can read as a probability">Scores from the lead ranker are isotonic-calibrated: on held-out worlds the expected calibration error is 0.002, so a 90% lead is right about nine times in ten. Rule-scored lead types (peel chains, unusual transactions) are labelled as evidence scores instead.</Callout>
      </section>

      <section id="data" aria-labelledby="h-data">
        <h2 id="h-data" className="section-title">The data contract</h2>
        <p className="section-sub" style={{ marginBottom: 12 }}>The minimum fields named by the problem statement. Missing optional fields degrade gracefully: stages that need them switch off and the dataset X-ray says so.</p>
        <div className="panel"><div className="table-wrap"><table className="data-table"><thead><tr><th>Field</th><th>Handling</th></tr></thead><tbody>{FIELDS.map(([f, d]) => <tr key={f}><td className="num">{f}</td><td>{d}</td></tr>)}</tbody></table></div></div>
      </section>

      <section id="eval" aria-labelledby="h-eval">
        <h2 id="h-eval" className="section-title">Evaluation, honestly</h2>
        {ev ? (
          <div className="stats" style={{ marginTop: 12 }}>
            <div className="stat"><b>{pc(ev.origin_top1_mean)}</b><span>origin IP first try (random guess {pc(ev.origin_random_baseline_mean)})</span></div>
            <div className="stat"><b>{pc(ev.origin_top3_mean)}</b><span>origin IP in the top 3</span></div>
            <div className="stat"><b>{pc(ev.wallet_cluster_purity_mean)}</b><span>wallet clusters pure against hidden truth</span></div>
            <div className="stat"><b>{ev.observable_transactions_total}</b><span>observable transactions across {ev.seeds.length} unseen worlds</span></div>
          </div>
        ) : <Skeleton lines={2} />}
        <p className="note" style={{ marginTop: 10 }}>Splits are by world, never by row. <a href={DOC("EVAL.md")} target="_blank" rel="noreferrer">The full table ↗</a> is regenerated by <span className="mono">sutradhar evals report</span> against freshly generated worlds, not hand-typed.</p>
      </section>

      <section id="trust" aria-labelledby="h-trust">
        <h2 id="h-trust" className="section-title">Security and lawful use</h2>
        <ul className="reasons" style={{ marginTop: 12 }}>
          <li><b>Offline by construction.</b> An in-process guard refuses outbound sockets; CI runs the self-test with the network disabled.</li>
          <li><b>Tamper-evident.</b> Audit log is hash-chained; evidence packs are sealed with per-file SHA-256 and an HMAC. <a href={href("verify")}>Try breaking one.</a></li>
          <li><b>Least privilege.</b> A permission matrix per role is declared on every route and tested; demo visitors are isolated from each other.</li>
          <li><b>Hostile input.</b> XML entities and billion-laughs are refused; uploads are size-capped, validated row by row and deleted after an hour.</li>
          <li><b>Leads, not verdicts.</b> Language is guarded, exports are watermarked as synthetic, and every flag carries its counter-evidence.</li>
          <li><b>Reviewed.</b> <a href={DOC("SECURITY_PASS.md")} target="_blank" rel="noreferrer">The security pass ↗</a> lists every threat considered and the test that pins it.</li>
        </ul>
      </section>

      <section id="limits" aria-labelledby="h-lim">
        <h2 id="h-lim" className="section-title">Where we are candid about limits</h2>
        <ul className="reasons" style={{ marginTop: 12 }}>
          <li>All data is synthetic. The generator is realistic by design and checked against stated realism bands (<span className="mono">sutradhar gen validate</span>), but real traffic will be messier.</li>
          <li>The origin model beats the earliest-announcer rule by only a few points, and both sit close to the ceiling the sensor placement allows. The value is the evidence, clustering and explanation around the origin call.</li>
          <li>The CoinJoin classifier matches, rather than beats, the heuristic it replaced on our generated worlds, whose look-alikes are easy negatives. Real-world recall will be lower.</li>
          <li>Peel-chain hop precision is modest; published CHAIN leads, which add structure checks, are 100% real chains on the test worlds.</li>
        </ul>
        <p className="note" style={{ marginTop: 10 }}>Longer write-up: <a href={DOC("TECHNICAL_WRITEUP.md")} target="_blank" rel="noreferrer">technical write-up ↗</a> · <a href={REPO} target="_blank" rel="noreferrer">repository ↗</a></p>
      </section>
    </div>
  );
}
