import { HERO } from "./guide";
import { href } from "./router";

export type Status = "live" | "part" | "next";
export type Req = { id: string; title: string; status: Status; how: string; to?: string; cta?: string; external?: boolean };

const REPO = "https://github.com/Abhishek222983101/sutradhar-btc";
const DOC = (name: string) => `${REPO}/blob/main/docs/${name}`;
const lead = (tab: string, who = HERO.wallet) => href("console", { lead: who, tab });

// The problem statement, clause by clause, with what is actually running today and a link that opens the proof.
export const REQUIREMENTS: Req[] = [
  { id: "01", title: "Complete offline system", status: "live", how: "Proven with the network disabled: the self-test runs in a container with --network none in CI, an in-process guard refuses outbound sockets, and the compose stack has no route to the internet.", to: href("system"), cta: "See the offline proof" },
  { id: "02", title: "Ingest bulk CSV / JSON / XML", status: "live", how: "CSV, TSV, JSON, NDJSON and XML (attack-safe) with mapping profiles, an auto-mapper, a rejects report and a dataset X-ray. Sample files are one click away.", to: href("console", { section: "upload" }), cta: "Upload a sample file" },
  { id: "03", title: "Correlate network with blockchain", status: "live", how: "Sensor timing gives a posterior over origin IPs per transaction, joined to wallet clusters.", to: lead("network"), cta: "See the IP behind a wallet" },
  { id: "04", title: "AI/ML anomalies, clusters, ranked leads", status: "live", how: "Isolation Forest anomalies, wallet clustering and a calibrated LightGBM ranker turn everything into one evidence-ranked list.", to: href("console"), cta: "Open the ranked leads" },
  { id: "05", title: "Parse all required fields", status: "live", how: "Time, IPs, ports, TXID, addresses, amounts in exact satoshis, fee and script type (inferred from the address when absent).", to: href("console", { section: "xray" }), cta: "See the dataset X-ray" },
  { id: "06", title: "Entity graph of IPs, wallets, txs", status: "live", how: "Wallet clusters, IPs and transactions are linked by evidence-tagged edges (value flow, origin, co-origin, taint path).", to: lead("evidence"), cta: "Open the link graph" },
  { id: "07", title: "A working model, not just rules", status: "live", how: "Trained models with published metrics against rule baselines: LightGBM lead ranker, origin-IP model, change-address model, Isolation Forest and the CoinJoin classifier.", to: href("how"), cta: "See every model and its metrics" },
  { id: "08", title: "Ranked, explainable alerts with confidence", status: "live", how: "Every lead has a calibrated score, a grade, TreeSHAP reasons, the evidence against it and a what-if.", to: lead("why"), cta: "Read why a lead was flagged" },
  { id: "09", title: "Dashboard / link analysis", status: "live", how: "The analyst console: ranked leads, evidence tabs, link graph, Sankey value flows and propagation replay.", to: href("console"), cta: "Open the console" },
  { id: "10", title: "Entity clustering", status: "live", how: "Common-input ownership with a CoinJoin guard and a change-address model, plus graph embeddings and analyst-approved merge suggestions.", to: lead("members"), cta: "See a wallet's members" },
  { id: "11", title: "Anomaly detection", status: "live", how: "Unsupervised Isolation Forest over value, fee rate and split shape, shown as its own evidence family.", to: href("console", { filter: "TX" }), cta: "See unusual transactions" },
  { id: "12", title: "Peeling chains and mixing", status: "live", how: "Peel-chain traversal and a CoinJoin detector that keeps mixes out of wallet clustering.", to: href("console", { filter: "CHAIN" }), cta: "See a peeling chain" },
  { id: "13", title: "Risk propagation from seed wallets", status: "live", how: "Value-weighted haircut taint with hop decay, personalised PageRank and k-best paths from a watchlist.", to: lead("path", HERO.multiHop), cta: "Follow a path to a seed" },
  { id: "14", title: "Synthetic dataset like real P2P data", status: "live", how: "In-house world generator: UTXO ledger, Bitcoin-style relay timing, sensors, hidden ground truth, four observation models.", to: href("scenarios"), cta: "See the scenarios" },
  { id: "15", title: "Minimum dataset fields", status: "live", how: "Exactly the specified columns, plus optional fee, script type, country and ASN, in CSV, JSON, NDJSON or XML.", to: href("console", { section: "upload" }), cta: "Download a sample" },
  { id: "16", title: "Open-source GeoIP database", status: "live", how: "DB-IP Lite (CC BY 4.0) bundled offline; every IP gets country and ASN with its source and date.", to: href("system"), cta: "See the bundled data" },
  { id: "17", title: "Offline solution for Linux", status: "live", how: "docker compose up gives the full offline product (web, API, worker) on any Linux host; sutradhar selftest verifies it.", to: REPO, cta: "See the install steps", external: true },
  { id: "18", title: "Working prototype, code repo", status: "live", how: "Monorepo with CI, tests, import-boundary contracts and a security gate.", to: REPO, cta: "Open the repository", external: true },
  { id: "19", title: "Short technical write-up", status: "live", how: "Approach, model choice and explainability method, with every number reproducible and the limits stated.", to: DOC("TECHNICAL_WRITEUP.md"), cta: "Read the write-up", external: true },
  { id: "20", title: "Flagged entities with evidence per flag", status: "live", how: "Open any lead: reasons, candidate IPs with probabilities, transactions, a sealed evidence pack.", to: lead("why"), cta: "Open a flagged entity" },
];
export const LABEL: Record<Status, string> = { live: "Live", part: "In progress", next: "Next" };
