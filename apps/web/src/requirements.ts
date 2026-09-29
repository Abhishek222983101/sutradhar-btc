export type Status = "live" | "part" | "next";
export type Req = { id: string; title: string; status: Status; how: string; link?: string };

// The problem statement, clause by clause, with what is actually running today. Honest by design.
export const REQUIREMENTS: Req[] = [
  { id: "01", title: "Complete offline system", status: "part", how: "Outbound-network guard is active and audited; runs with no internet. Air-gapped bundle is next.", link: "#/console" },
  { id: "02", title: "Ingest bulk CSV / JSON / XML", status: "part", how: "Streaming CSV/TSV with mapping profiles, rejects report and dataset X-ray. JSON and XML readers are next.", link: "#/console" },
  { id: "03", title: "Correlate network with blockchain", status: "live", how: "Sensor timing gives a posterior over origin IPs per transaction, joined to wallet clusters.", link: "#/console" },
  { id: "04", title: "AI/ML anomalies, clusters, ranked leads", status: "live", how: "Isolation Forest, wallet clustering and an evidence-ranked lead list.", link: "#/console" },
  { id: "05", title: "Parse all required fields", status: "live", how: "Time, IPs, ports, TXID, addresses, amounts in satoshis, fee, script type from address.", link: "#/console" },
  { id: "06", title: "Entity graph of IPs, wallets, txs", status: "part", how: "Every lead shows its IP, wallet cluster and transactions with evidence. Full canvas is next.", link: "#/console" },
  { id: "07", title: "A working model, not just rules", status: "part", how: "Trained Isolation Forest is live. The origin scorer is a transparent timing model; a learned ranker is next." },
  { id: "08", title: "Ranked, explainable alerts with confidence", status: "live", how: "Every lead has a score, a grade, plain-language reasons and a hedged summary.", link: "#/console" },
  { id: "09", title: "Dashboard / link analysis", status: "live", how: "The analyst console: ranked leads, evidence, propagation replay.", link: "#/console" },
  { id: "10", title: "Entity clustering", status: "part", how: "Common-input ownership with a CoinJoin guard: 100% pure on the test world. Embeddings are next.", link: "#/console" },
  { id: "11", title: "Anomaly detection", status: "live", how: "Unsupervised Isolation Forest over value, fee rate and split shape.", link: "#/console" },
  { id: "12", title: "Peeling chains and mixing", status: "part", how: "Peel-chain traversal is live; CoinJoin-shaped transactions are excluded from clustering.", link: "#/console" },
  { id: "13", title: "Risk propagation from seed wallets", status: "live", how: "Value-weighted haircut taint from a watchlist, shown as evidence on leads.", link: "#/console" },
  { id: "14", title: "Synthetic dataset like real P2P data", status: "live", how: "In-house world generator: UTXO ledger, Bitcoin-style relay timing, sensors, hidden ground truth." },
  { id: "15", title: "Minimum dataset fields", status: "live", how: "Exactly the specified columns, plus optional fee, script type, country, ASN." },
  { id: "16", title: "Open-source GeoIP database", status: "next", how: "Country/ASN columns are ingested; bundling an open GeoIP database is next." },
  { id: "17", title: "Offline solution for Linux", status: "part", how: "Everything runs from one command on Linux today; installer bundle is next.", link: "https://github.com/Abhishek222983101/sutradhar" },
  { id: "18", title: "Working prototype, code repo", status: "live", how: "Monorepo with CI, tests and a security gate.", link: "https://github.com/Abhishek222983101/sutradhar" },
  { id: "19", title: "Short technical write-up", status: "part", how: "Approach and honest metrics are in the repo and on this page; PDF is next.", link: "https://github.com/Abhishek222983101/sutradhar" },
  { id: "20", title: "Flagged entities with evidence per flag", status: "live", how: "Open any lead: reasons, candidate IPs with probabilities, transactions, replay.", link: "#/console" },
];
export const LABEL: Record<Status, string> = { live: "Live", part: "In progress", next: "Next" };
