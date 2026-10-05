# Demo script and speaker's guide

For recording the SIH video and for answering judges. Every number below is from `docs/EVAL.md` or read from the running
hero dataset; every click path was run in a real browser (`apps/web/scripts/e2e-judge-flow.mjs`, 19/19 passing).

Live site: https://sutradhar-one-red.vercel.app (Judge guide at `#/guide`).

---

## 1. Before you record (5 minutes)

1. Open the site **3 minutes before** recording so the free server is awake (header pill says "Server live").
2. Use Chrome, window about 1440x900, browser zoom 100%. Close other tabs and notifications.
3. Open the site once, press **Start the 8-minute tour**, then press **Close** on the tour card (a card in the corner
   looks busy in a video). Press **Hide** on "How to use the Console" if it is open.
4. Download the three sample files from the Console (left column, "No file handy?") so they are in your Downloads folder.
5. Do **not** record the first load of the day. A cold server shows the "Waking server" banner for up to 45 seconds.
6. The upload analysis takes **1 to 2 minutes** on the free host. Either speed that part up in editing, or start the upload,
   talk over the explanation scene while it runs, and come back to it (script below does this).

---

## 2. Eight-minute video, scene by scene

Speak slowly. Each scene lists: **screen**, **do**, **say**, **you will see**, **tech to name**.

### Scene 1: The problem (0:00 to 0:40), landing page `#/`

- **Say:** "Bitcoin addresses are pseudonymous, but the network is not. The node that first announces a transaction leaves
  a timing trace at any listening sensor. NTRO's problem statement asks for an offline system that joins that network
  layer to the blockchain layer, uses a real ML model rather than rules, and gives investigators a ranked, explainable
  list of leads. This is Sutradhar. It runs completely offline, and everything you see today is on synthetic data."
- **Point to:** the headline "Find the IP behind the wallet", the 4 stat tiles.
- **Say (numbers, exactly):** "On five freshly generated worlds the system finds the true origin IP on the first try
  39.1% of the time, against 4.4% for random guessing and 37.5% for the classic earliest-announcer rule. The theoretical
  ceiling is 67.8%, because in a third of cases no sensor ever heard the origin. We report this honestly: our value is
  not a magic origin model, it is the evidence, clustering and explanation built around it."

### Scene 2: Every requirement is linked (0:40 to 1:10), scroll the board

- **Do:** scroll the "problem statement, line by line" board.
- **Say:** "Each of the twenty requirements in the problem statement is a card. Every card says what runs today and links
  to the live page that proves it. Judges can click any of them. There is also a Judge guide with the exact inputs."
- **Do:** click **Judge guide** in the header for two seconds, then come back.

### Scene 3: The ranked leads (1:10 to 2:00), Console `#/console`

- **Do:** click **Open the console**. Hover the first lead.
- **Say:** "This is the answer to the problem statement: a ranked list of leads, most urgent first. 27 leads in this
  dataset: wallet groups, cash-outs, shared-IP leads, a peeling chain and unusual transactions. The letter is a grade, the
  bar is a calibrated confidence."
- **Click:** the first lead, "Wallet group bc1q5frsvq…".
- **You will see:** 100% calibrated confidence, grade A, four chips ANOM, FLOW, NET, TAINT, value 0.5204 BTC.
- **Say:** "Grade A means at least 80% confidence and at least three independent kinds of evidence agree. The wording
  here is deliberate: 'a lead for review, not a finding about anyone.' Our language guard forbids stating guilt."
- **Tech:** LightGBM ranker, about 36 features in five families, isotonic calibration (expected calibration error 0.002).

### Scene 4: Why was it flagged (2:00 to 3:15), tab **Why**, then **What-if**

- **Click:** tab **Why**.
- **You will see:** bars. Top one: "About 95% of its funds can be traced back to a watchlisted wallet" (weight 5.57).
- **Say:** "Every row is one piece of evidence, sized by how much it moved the score. These are TreeSHAP values from the
  trained model, so they are exact, not an approximation. The grey line names the evidence family and the model feature."
- **Scroll to** "Against this reading": "Little of what it sends goes to exchanges" and "The network evidence for the origin
  IP is weak (72%)".
- **Say:** "The system argues against itself. A lead without counter-evidence is a verdict, and we do not do verdicts."
- **Click:** tab **What-if**.
- **You will see:** "Resetting taint_max to typical on its own would not move the score. Other evidence holds it at 100%".
- **Say:** "A counterfactual: we reset the strongest evidence to a typical value and re-score. Here the score does not move,
  because other evidence already saturates it. We print that rather than invent a number."

### Scene 5: The IP behind the wallet (3:15 to 4:15), tabs **Network** and **Evidence**

- **Click:** **Network**.
- **You will see:** a table: 40.94.238.111, IN, AS8075 Microsoft Corporation, confidence about 70%; 82.38.98.96, GB, NTT.
- **Say:** "This is the headline capability. Each row is an IP the sensors heard announcing this wallet's transactions first,
  with the model's probability. Country and AS come from an offline GeoIP database, with its source and date shown. These
  IPs are synthetic, drawn from real country and AS blocks, not real people."
- **Click:** **Evidence**, then **Replay** on the first transaction.
- **You will see:** dots appear over about 1.5 seconds; the orange dot, the suspected origin, appears first.
- **Say:** "That is the first 1.5 seconds of one transaction spreading, as five listening sensors heard it. The origin model
  is a logistic regression on timing features, and it is tested on worlds it has never seen."
- **Click:** **Investigate graph**.
- **Say:** "The entity graph: wallet cluster, its IPs and neighbours. Edge colours are relationship types: value flow,
  origin, co-origin, taint path. It is laid out in your browser with no external library."

### Scene 6: Following the money (4:15 to 5:00), deep link `?lead=bc1q9506uy&tab=path`

- **Do:** click the lead "Wallet group bc1q9506uy…" then tab **Path to seed**.
- **You will see:** 6% taint, 3 hops, PageRank 0.037; a path of four boxes from an orange "seed" to "this wallet".
- **Say:** "Risk propagates from seed wallets an investigator already knows. This watchlist has two: a ransomware address
  and a darknet-market address. This wallet is three payments downstream. Taint is a value-weighted haircut: it shrinks
  with every hop (decay 0.97) and it stops at exchanges, so an innocent customer who received money from an exchange is not
  marked. Alongside it we run personalised PageRank, and the explaining path is the cheapest route through the money flow."

### Scene 7: Search everything (5:00 to 5:30), omnibox

- **Do:** click the search box. Type, one at a time, picking the dropdown result each time:
  1. `40.94.238.111` → IP dossier.
  2. `AS8075` → list of IPs on that AS; click one IP chip to drill in.
  3. `7de132c3ca` → an "Unusual payment" lead (Transaction tab).
  4. `bc1q64weeskl8vkre5urxq24yfpp2xtf9xpjzlmskq` → address dossier.
- **Say:** "One box understands transaction ids, addresses, IPs, AS numbers and wallet groups, and every result opens a page
  with labelled facts, not raw JSON."

### Scene 8: Peeling chains, mixing, anomalies (5:30 to 6:00)

- **Do:** click the **Peel chain** chip, then **Unusual tx**, then scroll down to "What the engine did".
- **Say:** "The three focus areas the problem statement names. A peeling chain is a launderer repeatedly spending, paying a
  small amount and sending the rest onward. The system found one chain of five hops and published it at 92%. Unusual transactions
  come from an Isolation Forest. And in the pipeline panel, stage E04 is CoinJoin detection, now a trained classifier, which
  also keeps mixing transactions from wrongly merging unrelated wallets."

### Scene 9: Bring your own data (6:00 to 7:00), left column upload

- **Do:** drop `sutradhar-sample.csv` on "Try your own file". Say the next lines **while it runs** (about 1 to 2 minutes).
- **Say:** "Ingestion in CSV, JSON, NDJSON and XML, hostile-input safe. Amounts are parsed as decimals and stored as integer
  satoshis, never floats. Rows that break a rule are refused with the rule named. After ingestion the 21-stage engine
  runs on a deliberately small free server, which is why it takes a minute or two here; the same file takes about seven seconds on a laptop."
- **You will see:** status line "Loaded 3060 rows, 255 transactions, 0 rejected, observation model: vantage", then
  "Done: 14 leads found in your upload".
- **Do:** scroll to the Dataset X-ray at the bottom of the right column. **Say:** "The X-ray tells you what this data
  allows: observation model, sensors detected, which analysis stages it enabled."

### Scene 10: Cases and the tamper-evident evidence (7:00 to 7:50), `#/cases` then `#/verify`

- **Do:** Cases → title `Peeling-chain investigation` → **Create case**; note `Taint path checked: 3 hops from the seed wallet.` → **Add note**; press **Export** on the evidence pack and click **download**.
- **Say:** "A case is the hand-off: notes plus four export formats, including MISP and GraphML for the tools investigators already use."
- **Do:** Verify → **1. Build a sample pack and verify it** (green VALID) → **2. Edit a file, then verify** (red, names notes.md) → **3. Edit the file and forge its hash, then verify** (red, "seal does not match").
- **Say:** "Every file in an evidence pack is hashed into the manifest, and the manifest is sealed with an HMAC only the issuing
  server can produce. Edit a file and the hash fails. Edit the manifest to match, and the seal fails. This is for chain of
  custody."

### Scene 11: Offline proof and the models (7:50 to 8:30), `#/system`, `#/how-it-works`

- **Do:** System: point at "AIR-GAPPED ✓", the blocked-connection counter, the three reference files marked intact, the
  audit chain "Intact". Then How it works: scroll the architecture picture and the four model cards.
- **Say:** "The problem statement requires the solution to work offline. The application refuses outbound sockets, CI runs the
  full self-test in a container with the network physically disabled, and the GeoIP data and model weights ship inside the
  bundle. Four trained models: the lead ranker, the origin model, the change-address model and the CoinJoin classifier, plus
  an Isolation Forest, each with metrics against a rule baseline."

### Scene 12: Close (8:30 to 9:00)

- **Say:** "What we are candid about: all data is synthetic; the origin model beats the classic rule by only a few points and
  both sit near the ceiling the sensor placement allows; the CoinJoin classifier matches rather than beats the rule it
  replaced on our generated worlds. What we are proud of: the whole pipeline is reproducible from a seed, every claim has its
  evidence, and every number on screen is regenerated by one command."

> Total is just under nine minutes. If you need seven, drop scene 8 and compress scene 2.

---

## 3. Page-by-page test checklist

| Page | Do | Input | Expect |
|---|---|---|---|
| Landing `#/` | Start the tour | none | lands on Judge guide, "0 of 8 core checks done" |
| Console | open first lead | none | 100%, grade A, chips ANOM/FLOW/NET/TAINT |
| Console tabs | click all 8 | none | each tab loads (skeleton then content), no red box |
| Console search | type | `40.94.238.111`, `AS8075`, `7de132c3ca`, `bc1q64weeskl8vkre5urxq24yfpp2xtf9xpjzlmskq` | dropdown, then a dossier or lead |
| Console filters | click chips | Peel chain, Unusual tx, Cash-out, IP | list narrows; peel chain shows 1 lead |
| Console upload | choose file | `sutradhar-sample.csv` | "Done: 14 leads found" after 1-2 min |
| Cases | create, note, 4 exports | title `Peeling-chain investigation` | each export "ready" with a sha256; download works |
| Verify | press 1, 2, 3 | none | VALID; FAILED (notes.md); FAILED (seal) |
| Govern | read | none | 4 model cards, settings, "Chain intact"; recent activity says needs lead role |
| System | read | none | AIR-GAPPED ✓, 3 files intact |
| How it works | scroll | none | SVG diagram, 21 stage cards, 4 model cards, eval numbers |
| Academy | Start, answer 5, Submit | any | a percentage score |
| Scenario Studio | read | none | tiny/demo/rich/hard cards with commands |
| Hindi toggle | click हिं | none | nav and titles in Hindi (chrome only) |

If a page shows a red "This part could not load" box, press **Try again** once: the free server may have been waking.

---

## 4. What we built, in depth (so you can explain it)

### 4.1 The problem in one paragraph

A Bitcoin transaction has two lives. On the **ledger** it is inputs and outputs: addresses and amounts. On the **network** it
is a message flooding across peers: some node announced it first, then its neighbours, then theirs. Ledger data says *what
moved*, network data says *from where*. NTRO's problem statement asks for a system that links the two so an investigator can
go from a suspicious wallet to the IP that likely broadcast its transactions, with ML, ranking and explanations, offline.

### 4.2 The data and why it is synthetic

No dataset is provided and real data would be unlawful to ship, so we built a generator (`packages/generator`).
- A **UTXO ledger** with exact satoshis, wallets, coin selection (largest-first, FIFO, random), change outputs, fees.
- **Agents**: ordinary users, exchanges, merchants, payroll, trading bots, mining pools, gambling sites, a CoinJoin
  coordinator, a ransomware operation (collects ransoms, launders through a peeling chain, cashes out), a darknet market.
- A **P2P network**: Bitcoin-style diffusion, where each node announces a transaction to each peer after a random delay
  (mean 2 s to outbound peers, 5 s to inbound) plus link latency; five silent **sensors** record the first announcements they hear.
- **Hidden ground truth** (who really owns what, which IP really originated each transaction) used only by the evaluation code.
  An import-boundary check in CI makes it impossible for the engine to read it.
- Four **observation models** (vantage sensors, ISP-style flow sampling, mixed, single-report) so the engine is tested on
  different ways a real capture could look. Domain randomisation and a realism report (`sutradhar gen randomize|validate`).
- Everything is **deterministic**: same scenario and seed gives byte-identical output.

The demo dataset ("hero") is scenario `rich`, seed 2: 1,145 transactions, 28,625 network sightings, 2,621 addresses, 105 IPs, 5 sensors.

### 4.3 The pipeline: 21 stages

Per run, a fixed sequence writes tables into a DuckDB file and a digest (identical input gives an identical digest).

| Group | Stages | What they do |
|---|---|---|
| Load and enrich | E01, E02 | freeze the dataset, add country and ASN from the bundled DB-IP Lite database |
| Chain | E03 flows, E04 CoinJoin, E05 clustering, E06 change, E07 peel chains | who pays whom; mixing; which addresses are one wallet; which output is change; spend-peel-forward chains |
| Network | E09 origin, E11 co-origin | which IP first announced each transaction; wallets that keep sharing an origin IP |
| Risk | E13 taint, E20 services, E21 paths | haircut taint from seeds; exchanges excluded; PageRank and k-best paths |
| ML | E08 anomaly, E12 embeddings, E14 fingerprints, E15 motifs, E22 features, E17 ranking | Isolation Forest; 16-dimension graph embeddings; behaviour vectors; about 36 features; the calibrated ranker |
| Explain and publish | E16 merge suggestions, E18 explanations, E19 publish | operator-sharing suggestions; reasons, counter-evidence, what-ifs; invariants and digests |

### 4.4 Key ideas, in plain terms

- **Common-input-ownership (CIOH).** If a transaction spends coins from addresses A, B and C, one party signed for all three,
  so A, B, C are one wallet. We union them. The weakness is **CoinJoin**: a transaction built by several people, where the
  inputs belong to different owners. Our trained CoinJoin classifier flags those and the clustering refuses to merge their
  inputs (invariant I8). This is why CoinJoin detection matters to clustering accuracy: without it, wallets get fused wrongly.
  Cluster purity against hidden truth is 99.9%; merging CoinJoins would drop it to 99.5%.
- **Change address.** When you pay 0.01 BTC from a 0.5 BTC coin, the remainder returns to a fresh address of yours. Identifying
  that output links the next spend back to the same wallet. A logistic model identifies it correctly 95.2% of the time, and we
  only use links above 0.99 confidence (precision 99.6%), because looser links added reach but lowered purity.
- **Peeling chain.** A launderer's pattern: spend a large coin, pay a small amount, send the large remainder to a new address, repeat.
  We walk timing-aware chains (at least three hops, one hour gap). Published CHAIN leads are 100% real chains; hop-level precision is 37.1% (recall 100%), and we say so.
- **Origin attribution.** For each transaction the sensors give an ordered list of who announced it to them. The earliest
  announcer is often the origin or its first hop. Our model scores each candidate IP using timing features and returns a
  probability. Benchmarks: 39.1% top-1 vs 37.5% earliest-announcer vs 4.4% random; 51.5% in the top three; ceiling 67.8%.
- **Taint and PageRank.** Taint: if a seed wallet pays X, X inherits a share proportional to value, multiplied by 0.97 for each
  further hop, and propagation stops at exchanges. Personalised PageRank (damping 0.85) asks "how reachable is this wallet
  from the seeds?", which is what the "Path to seed" tab draws.
- **Anomaly detection.** An Isolation Forest scores how easy it is to isolate a transaction by its value, fee rate and split
  shape. It is unsupervised, so it needs no labels and surfaces what is merely unusual (the TX leads, grade C).
- **The lead ranker (the main ML model).** LightGBM trained on 30,439 wallet clusters (430 illicit) across three scenarios,
  including a "hard" one with benign look-alikes (merchants, payroll, traders, pools, gambling) as negatives. PR-AUC 0.983 with
  watchlist seeds and 0.980 **without** them, which proves it is not just copying taint. Raw tree scores are not
  probabilities, so we apply **isotonic calibration**: expected calibration error 0.002, meaning "90%" is right about 9 times in 10.
- **Explainability.** (1) TreeSHAP splits each score into one contribution per feature. (2) Templates turn features into
  plain sentences, checked by a language guard that forbids identity or guilt claims. (3) Opposing evidence and a counterfactual
  (reset the strongest evidence to typical, re-score) are published with every lead.
- **Evaluation protocol.** Train and test on **different worlds**, never different rows of one world (row splits leak
  neighbouring transactions and inflate results). Each model is compared with a rule baseline. Hidden truth is read only by `packages/evals`.
- **Offline guarantee.** An in-process guard refuses outbound sockets; the CI job runs the self-test with `docker run --network none`;
  GeoIP data and model weights are inside the bundle; nothing downloads at run time.
- **Tamper evidence.** The audit log is hash-chained (each entry hashes the previous one). Evidence packs hash each file and
  HMAC-seal the manifest.

### 4.5 Architecture

- `packages/schemas`: the data contract (fields, units, evidence envelope). Imports nothing internal.
- `packages/engine`: ingest plus the 21 stages plus model weights plus bundled GeoIP.
- `packages/generator`: synthetic worlds with hidden truth.
- `packages/evals`: training and evaluation (the only code that reads truth).
- `packages/cli`: the `sutradhar` command (`gen`, `ingest`, `run`, `evals`, `selftest`).
- `apps/api`: FastAPI, auth with refresh rotation, role permission matrix, job queue with an embedded worker, audit chain, offline guard.
- `apps/web`: React 19 and Vite console, with no external fonts, scripts or network calls (a CI check scans the built bundle).
- Deployment: web on Vercel, API on Render (demo mode, SQLite, hero world pre-built and unpacked at boot). The air-gapped
  `compose.airgap.yaml` is the real deliverable for NTRO.

### 4.6 What is honestly not done

- The adversary red-team report, GraphSAGE and Elliptic++ comparisons and the sensor-placement planner (stretch items).
- A retrain-shadow-promote pipeline (the feedback API exists, retraining is by CLI).
- Co-origin crowdedness correction and sensor clock-skew correction.
- Full accessibility audit and full Hindi translation (the toggle covers navigation and titles).
- Real-world validation: everything is on synthetic data, and recall on real CoinJoins will be lower.

---

## 5. Questions judges may ask

1. **Why synthetic data?** None is provided and real traffic could not lawfully be shipped. We built a generator with hidden
   ground truth, which also lets us measure accuracy, which real data never can.
2. **Only 39% origin accuracy?** The ceiling is 67.8% (the origin must reach a sensor), the classic rule gets 37.5% and a
   random guess 4.4%. The gain is the pipeline around it: clustering, risk, calibrated ranking and explanation.
3. **Is it just rules?** No: the ranker, origin, change and CoinJoin models are trained and evaluated against rule baselines.
   Honest note: the CoinJoin model matches the old rule on our generated worlds.
4. **How do you avoid falsely accusing someone?** Leads are hedged by a language guard, carry counter-evidence, expose a
   calibrated probability, stop taint at exchanges, and nothing merges without an analyst's audited decision.
5. **How do we know it works offline?** `docker run --network none ... sutradhar selftest` in CI, plus the System page.
6. **What about Tor and VPNs?** A reference-range hook tags known Tor exit and VPN ranges (it ships empty; a maintainer
   refreshes it online, never the product). Origin attribution in those cases would point at the exit, and the lead says so.
7. **Why LightGBM?** Strong on skewed tabular features, exact TreeSHAP explanations, fast on CPU.
8. **What is calibration?** Making "90%" mean 90%. We use isotonic regression; expected calibration error is 0.002.
9. **How does it scale?** Each run is a columnar DuckDB store; stages are vectorised. The demo runs on a throttled free CPU
   (the 255-transaction sample takes about 90 seconds there); a laptop does it in about seven seconds.
10. **What is your next step?** Real-data pilots on a sensor feed, a retrain loop driven by analyst feedback, and stronger
    adversary testing (the red-team report we cut for time).
