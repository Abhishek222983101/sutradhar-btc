import type { Page, Params } from "./router";

// The judge guide, as data. Every page's "How to use this page" panel, the floating tour and the Guide page read from
// here, so the instructions cannot drift apart. Sample inputs are real values from the bundled hero dataset (the
// same synthetic world on every install), so each one is guaranteed to return something.
export type Input = { label: string; value: string; note?: string };

export type Step = {
  id: string;
  core?: boolean;
  title: string;
  where: { page: Page; params?: Params };
  summary: string;
  do: string[];
  inputs?: Input[];
  expect: string[];
  proves: string[];
  tech: string;
};

export const HERO = {
  wallet: "bc1q5frsvq",
  seedWallet: "bc1q5frsvqd7lcsza8p2cqxu3tj0paypfall2lmshe",
  multiHop: "bc1q9506uy",
  ip: "40.94.238.111",
  asn: "AS8075",
  tx: "7de132c3ca",
  address: "bc1q64weeskl8vkre5urxq24yfpp2xtf9xpjzlmskq",
  cashout: "bc1qnfv9yu",
};

export const STEPS: Step[] = [
  {
    id: "leads", core: true, title: "See the ranked leads",
    where: { page: "console" },
    summary: "The system's answer to the problem statement: a ranked, explainable list of what an investigator should look at first.",
    do: [
      "Open the Console. The left column is every lead, most urgent first.",
      "Read one row: the letter is the grade, the bar is the calibrated confidence, the title says what pattern was found.",
      "Click the first lead, \"Wallet group bc1q5frsvq…\". The right side loads everything the system knows about it.",
    ],
    expect: [
      "A 100% evidence score with grade A and four coloured evidence-family chips (ANOM, FLOW, NET, TAINT).",
      "A hedged one-sentence summary: it says \"a lead for review, not a finding about anyone\".",
    ],
    proves: ["R-04", "R-08", "R-20"],
    tech: "Leads come from stage E17 (a LightGBM ranker, isotonic-calibrated so 90% really means about 90%) and E19 (publish). A lead needs several independent evidence families to earn a high grade.",
  },
  {
    id: "why", core: true, title: "Read why it was flagged, and why it might be wrong",
    where: { page: "console", params: { lead: HERO.wallet, tab: "why" } },
    summary: "Explainability is a requirement, not a nice-to-have: every flag carries its reasons and its counter-arguments.",
    do: [
      "On the Why tab, read the bars: each row is one piece of evidence, sized by how much it moved the score.",
      "Switch to the Against tab. These are the signals that argue the lead is wrong.",
      "Switch to the What-if tab to see which evidence, if it looked normal, would change the score.",
    ],
    expect: [
      "Plain-English reasons such as \"About 95% of its funds can be traced back to a watchlisted wallet\".",
      "Under each reason: the evidence family, the model feature name and its weight.",
    ],
    proves: ["R-08", "R-20"],
    tech: "Reasons are TreeSHAP contributions from the trained ranker, rendered through language-guarded templates (they can never say \"is a criminal\"). The counterfactual re-scores the wallet with its strongest evidence reset to a typical value.",
  },
  {
    id: "path", core: true, title: "Follow the money back to a seed wallet",
    where: { page: "console", params: { lead: HERO.multiHop, tab: "path" } },
    summary: "Risk is propagated from known-bad seed wallets, so a wallet three hops away still lights up.",
    do: [
      "Open the Path to seed tab for \"Wallet group bc1q9506uy…\".",
      "Read the chain: it starts at a watchlisted seed wallet and ends at this wallet, hop by hop.",
      "Compare with bc1q5frsvq…: that one is itself a seed, at hop 0.",
    ],
    expect: [
      "A 3-hop path drawn as connected wallet nodes, plus the taint share and personalised-PageRank score.",
    ],
    proves: ["R-13"],
    tech: "E13 runs value-weighted haircut taint with hop decay (it stops at exchanges, so customers are not tainted) and E21 runs personalised PageRank plus k-best paths, which are what you see as the explanation.",
  },
  {
    id: "network", core: true, title: "Find the IP behind the wallet",
    where: { page: "console", params: { lead: HERO.wallet, tab: "network" } },
    summary: "The headline capability: joining network-layer observations (who announced a transaction first) to blockchain-layer wallets.",
    do: [
      "Open the Network tab. Each row is a candidate origin IP with a probability.",
      "Look at the country and AS columns, and the source and date beside them (GeoIP is an offline database).",
      "Then open the Evidence tab and press Replay to watch the first announcements arrive.",
    ],
    expect: [
      "A short table of IPs with country, ASN, organisation, number of transactions and mean confidence.",
      "In Replay, an orange dot (the suspected origin) appears before the others.",
    ],
    proves: ["R-03", "R-16"],
    tech: "E09 turns sensor timing into a trained origin-IP model (logistic regression, evaluated on unseen worlds against first-spy and random baselines); E11 links wallets that share origin IPs. Country and ASN come from the bundled DB-IP Lite database, tagged with source and as-of date.",
  },
  {
    id: "graph", title: "Open the link-analysis graph",
    where: { page: "console", params: { lead: HERO.wallet, tab: "evidence" } },
    summary: "The entity graph linking IPs, wallets and transactions.",
    do: [
      "On the Evidence tab, press \"Investigate graph\".",
      "Read the legend: edge colours are relationship types (value flow, origin, co-origin, taint path).",
    ],
    expect: ["A force-directed graph of the wallet cluster with its IPs, with the focal node highlighted."],
    proves: ["R-06", "R-09"],
    tech: "The graph is built server-side from evidence-tagged edges, bounded to 150 nodes, and laid out in your browser with a small force-directed algorithm (no graph library, no network call).",
  },
  {
    id: "search", core: true, title: "Search anything",
    where: { page: "console", params: { open: `ip:${HERO.ip}` } },
    summary: "One search box understands transaction ids, addresses, IPs, AS numbers and wallet groups.",
    do: [
      "Click the search box above the lead list and paste one of the values below.",
      "Pick a result from the dropdown. Results of type \"lead\" open that lead; the rest open a dossier page.",
    ],
    inputs: [
      { label: "IP address", value: HERO.ip, note: "opens the IP dossier: country, ASN, linked wallet groups" },
      { label: "AS number", value: HERO.asn, note: "finds every IP on that network" },
      { label: "Transaction id (prefix is enough)", value: HERO.tx, note: "an unusual-payment lead" },
      { label: "Wallet address", value: HERO.address, note: "an address dossier: script type, taint, in and out counts" },
      { label: "Wallet group", value: HERO.wallet, note: "the cluster and its lead" },
    ],
    expect: ["A dropdown under the box, then a dossier panel with labelled facts (no raw JSON)."],
    proves: ["R-05", "R-06"],
    tech: "The omnibox calls /runs/{id}/search, which resolves ids by prefix across transactions, addresses, IPs, ASNs and wallet clusters in the run's DuckDB store.",
  },
  {
    id: "mixing", title: "Peeling chains, mixing and anomalies",
    where: { page: "console", params: { filter: "CHAIN" } },
    summary: "The three focus areas the problem statement names: peeling chains, CoinJoin-style mixing and statistical anomalies.",
    do: [
      "Use the filter chips above the list: Peel chain shows \"Peeling chain of 5 steps\", Unusual tx shows anomaly leads.",
      "Scroll to \"What the engine did\" under the lead: stage E04 is CoinJoin detection, E07 peel chains, E08 the anomaly model.",
    ],
    expect: ["A 92% peeling-chain lead; a list of unusual transactions graded C; stage-by-stage counts."],
    proves: ["R-11", "R-12"],
    tech: "E04 scores equal-output mixing structures with a trained classifier and keeps CoinJoin participants out of wallet clustering; E07 walks timing-aware peel chains; E08 is an Isolation Forest over value, fee rate and split shape.",
  },
  {
    id: "members", title: "Which wallets belong to one operator?",
    where: { page: "console", params: { lead: HERO.wallet, tab: "members" } },
    summary: "Entity clustering: common-input ownership plus graph embeddings, with analyst-approved merges.",
    do: [
      "Open the Members tab: the addresses grouped into this wallet because they were spent together.",
      "Below them, look for merge suggestions: other wallets that probably share an operator, with reasons.",
    ],
    expect: ["A list of member addresses and, where they exist, suggestions with a score and plain-language reasons."],
    proves: ["R-10"],
    tech: "E05 clusters by common-input ownership (with a CoinJoin guard and a change-address model), E12 builds 16-dimension graph embeddings, E16 proposes merges. Nothing merges automatically: a lead analyst accepts or rejects, and the decision is audit-logged.",
  },
  {
    id: "upload", core: true, title: "Bring your own data",
    where: { page: "console", params: { section: "upload" } },
    summary: "Ingestion in three formats, validated, with a plain-language report of what was accepted and refused.",
    do: [
      "Download a sample file from the links in the upload box (CSV, JSON or XML: same content, three formats).",
      "Drop it on \"Try your own file\" and watch the status line: upload, read, normalise, analyse. On the small free server the analysis takes 1 to 2 minutes and the line shows each stage as it runs.",
      "When it finishes, the whole console switches to your upload. Open the Dataset X-ray at the bottom.",
    ],
    inputs: [
      { label: "Sample CSV", value: "sutradhar-sample.csv", note: "downloads from /samples" },
      { label: "Sample JSON", value: "sutradhar-sample.json" },
      { label: "Sample XML", value: "sutradhar-sample.xml" },
    ],
    expect: [
      "\"Loaded 3060 rows, 255 transactions, 0 rejected\" then \"Done: 14 leads found\".",
      "An X-ray that says the observation model is vantage, with the analysis stages it enabled.",
    ],
    proves: ["R-02", "R-05", "R-15"],
    tech: "Streaming readers for CSV, JSON, NDJSON and XML (entity-safe: XXE and billion-laughs are refused), exact-satoshi amounts, rule-tagged rejects, and a capability profile that switches stages off when fields are missing. Uploads are deleted after 60 minutes.",
  },
  {
    id: "verify", core: true, title: "Prove the evidence cannot be tampered with",
    where: { page: "verify" },
    summary: "Evidence packs are sealed: every file is hashed and the manifest carries an HMAC from the issuing server.",
    do: [
      "Press \"1. Build a sample pack and verify it\": the page creates a case, exports the evidence pack and checks it.",
      "Press \"2. Edit a file, then verify\": the page edits notes.md inside the zip the way an attacker would.",
      "Press \"3. Edit the file and forge its hash, then verify\": the smarter attacker who also fixes the manifest.",
    ],
    expect: [
      "First a green VALID verdict.",
      "Then a red FAILED verdict naming notes.md as changed after export; and a red FAILED verdict where the hashes agree but the seal does not.",
    ],
    proves: ["R-20"],
    tech: "The manifest lists each file's SHA-256 and is sealed with HMAC-SHA256 under the server's signing key, so editing a file fails the hash and editing the manifest to match fails the seal.",
  },
  {
    id: "cases", title: "Build a case file and export it",
    where: { page: "cases" },
    summary: "The hand-off: a working folder with notes and four export formats.",
    do: [
      "Create a case, add a lead from the Console (\"Add to case\"), write a note.",
      "Press each export: evidence pack, GraphML, MISP event, i2 CSV.",
    ],
    inputs: [
      { label: "Case title", value: "Peeling-chain investigation" },
      { label: "Note", value: "Taint path checked: 3 hops from the seed wallet, high confidence." },
    ],
    expect: ["A download link and the first 16 characters of the file's SHA-256 beside every export."],
    proves: ["R-20"],
    tech: "Exports are built inline and hashed; each one is audit-logged. MISP and GraphML open in the tools investigators already use.",
  },
  {
    id: "models", title: "Check the models behind the scores",
    where: { page: "govern" },
    summary: "A working AI/ML model, not just rules: every trained model with its training data and metrics.",
    do: ["Read the model cards: version, what it was trained on, held-out metrics.", "Then open How it works for why each model was chosen."],
    expect: ["Cards for the lead ranker, origin model, change-address model and the other trained models."],
    proves: ["R-07"],
    tech: "Every model is trained on generated worlds with hidden ground truth, split by world (never by row), and evaluated against rule baselines on seeds it never saw. docs/EVAL.md reproduces every number.",
  },
  {
    id: "offline", core: true, title: "Confirm it runs offline",
    where: { page: "system" },
    summary: "The problem statement says the solution must work with no internet. Here is the proof.",
    do: [
      "Read the AIR-GAPPED status and the counter of blocked outbound connections.",
      "Check the reference-data table: every bundled file with its source, date and checksum status.",
      "Copy the commands at the bottom to reproduce the proof on your own machine.",
    ],
    expect: ["A green offline guard, 0 blocked attempts, and reference files marked intact."],
    proves: ["R-01", "R-16", "R-17"],
    tech: "An in-process guard blocks any outbound socket to a public address (invariant I1); CI runs the self-test in a container with --network none; the bundle ships GeoIP data and model weights, so nothing downloads at runtime.",
  },
  {
    id: "tech", title: "Understand the engineering",
    where: { page: "how" },
    summary: "Architecture, the 21-stage pipeline, every model and how explanations are produced.",
    do: ["Read top to bottom, or jump to a section from the contents list."],
    expect: ["An architecture diagram, a stage table, live model metrics and the evaluation numbers."],
    proves: ["R-07", "R-19"],
    tech: "This page reads the live API for models and evaluation, so its numbers always match the running system.",
  },
  {
    id: "studio", title: "See the synthetic data",
    where: { page: "scenarios" },
    summary: "The dataset is synthetic by design and reproducible from a seed.",
    do: ["Read the four scenario presets and the exact command that regenerates each."],
    expect: ["tiny, demo, rich and hard, each with its size and the CLI line."],
    proves: ["R-14", "R-15"],
    tech: "The generator simulates a UTXO economy, Bitcoin-style relay timing, sensors and hidden ground truth. Same scenario and seed gives byte-identical output.",
  },
];

export const CORE_STEPS = STEPS.filter((s) => s.core);

export type PageHelp = { title: string; steps: string[]; inputs?: Input[]; tip?: string };

export const PAGE_HELP: Partial<Record<Page, PageHelp>> = {
  console: {
    title: "How to use the Console",
    steps: [
      "Pick a lead on the left. The grade and bar show how confident the system is.",
      "Use the tabs on the right: Summary, Why, What-if, Evidence, Network, Path to seed, Timeline, Members.",
      "Use the search box for any txid, address, IP, AS number or wallet group.",
      "Scroll to the bottom of the left column to upload your own file.",
    ],
    inputs: [
      { label: "Search an IP", value: HERO.ip },
      { label: "Search an AS number", value: HERO.asn },
      { label: "Search a transaction", value: HERO.tx },
    ],
    tip: "Every lead is a lead for review, never a statement about a person.",
  },
  cases: {
    title: "How to use Cases",
    steps: [
      "Type a title (3+ characters) and press Create case.",
      "Add leads from the Console with \"Add to case\", then come back and open the case.",
      "Write a note, then press an export button. Each export shows its SHA-256.",
    ],
    inputs: [{ label: "Case title", value: "Peeling-chain investigation" }],
  },
  govern: {
    title: "How to read Govern",
    steps: [
      "Model registry: every trained model, its version and training metrics.",
      "Settings: every threshold is a setting with its default; changed ones are marked.",
      "Audit chain: the append-only log. Demo visitors can check it is intact; reading entries needs a lead role.",
    ],
  },
  academy: {
    title: "How to use the Academy",
    steps: ["Press Start.", "Answer all five questions (one choice each).", "Press Submit: scoring happens on the server, which never sends the answers."],
  },
  scenarios: {
    title: "How to read Scenario Studio",
    steps: ["Each card is a synthetic world the generator can build.", "Copy the command to regenerate it on your own machine: same seed, byte-identical output."],
  },
  verify: {
    title: "How to use Verify",
    steps: [
      "Press \"1. Build a sample pack and verify it\" for a green result.",
      "Press \"2. Edit a file, then verify\" to see tampering caught, with the file named.",
      "Press \"3. Edit the file and forge its hash, then verify\" to see the seal catch a forged manifest.",
      "Or drop your own evidence pack (the zip from Cases) onto the box.",
    ],
  },
  system: {
    title: "How to read System",
    steps: ["Check AIR-GAPPED and the blocked-connection counter.", "Check the reference-data checksums.", "Copy the commands to reproduce the proof offline."],
  },
};
