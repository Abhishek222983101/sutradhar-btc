# SUTRADHAR — BITCOIN WIRE + LEDGER INTELLIGENCE — SYSTEM ARCHITECTURE & BUILD BLUEPRINT

> **Document:** `SUTRADHAR_PLATFORM_BLUEPRINT.md` · **Version** 1.0 · **Date** 2026-09-30
> **Built for** Smart India Hackathon 2026 · Problem Statement **SIH26146** · *AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic* · Organisation **National Technical Research Organisation (NTRO)** · Category **Software** · Theme **Blockchain & Cybersecurity**
> **Status** Pre-build. Design frozen for Phase 0.
> **Working name** *Sutradhar* (सूत्रधार, "the one who holds the strings"). It is a working title. Renaming is a find-and-replace done **before P0.1**, tracked as `[OPEN-01]`.
> **Source of truth for requirements** is the NTRO problem statement PDF (`~/Downloads/SIH26146.pdf`, 2 pages, scanned). The PS wins on **what** to build. This document wins on **how**.

---

## HOW TO READ THIS DOCUMENT

This document serves four audiences. Each can stop at a different point.

| If you are… | Read | Skip |
|---|---|---|
| **A teammate** who wants to know what we are building and why | **Part 1** and **Part 2** (~25 minutes, plain language) | Part 4 onward, until you pick up a module |
| **The person building a module** | Part 3 (architecture), then your part (4–14), then **your sub-phases in Part 15**, then Part 17 (appendices) | Other modules' deep sections |
| **An AI coding agent** building any part of this | **Everything.** Load §3.6 (invariants) and §17.15 (one-paragraph brief) into every session. | Nothing |
| **A mentor or judge** | Part 1, §2.2 (the PS, clause by clause), §3.1 (one-page architecture), Part 11 (how we measure ourselves) | The rest |

**Markers used throughout:**

| Marker | Meaning |
|---|---|
| `[PS]` | Traces directly to a clause of the NTRO problem statement. Not negotiable. |
| `[DECISION]` | A design decision made by us, always with its reason. It can be revisited if the reason changes. |
| `[DEFAULT]` | A running value used until an open question is answered. It lives in settings or config, never hard-coded. |
| `[OPEN]` | Unresolved. Listed in §16.1 with the item it blocks. |
| `[RISK]` | A known failure mode with a stated mitigation. Listed in §16.2. |
| `[STRETCH]` | Built only when every P0/P1-tier item in its phase is green. |

**On what we do not know yet.** NTRO has provided **no dataset** (the portal's "dataset" Google Drive link is the PS PDF itself). The finale date and the team's role split are also still unknown. This document does not wait on any of them. Each unknown becomes a **configuration surface or a generator parameter**, not an assumption baked into code. Examples:
- The input schema is described by a *mapping profile*, not by column names in code.
- The observation model (few sensors vs ISP-level flows) is *detected* from the data.
- Thresholds are *settings rows*.

When NTRO hands over a file at the finale, the system adapts by configuration. That is the design goal.

---


# PART 1 — WHAT WE ARE BUILDING, IN PLAIN LANGUAGE

*This part contains no technical detail. Anyone on the team, or any judge, should be able to read it.*

## 1.1 The problem, stated honestly

Bitcoin addresses are pseudonyms. Criminals use this to collect money (ransomware payments, darknet-market sales, extortion, scams), move it through layers of wallets, mix it, and cash it out at exchanges, without ever touching a bank that would know their name.

Two kinds of visibility exist, and they almost never meet:

1. **The ledger.** Every transaction is public. Anyone can analyse it, and commercial tools (Chainalysis, Elliptic, TRM) and open ones (GraphSense) do exactly that. The ledger shows *money moving between pseudonyms*. It does not show *who* or *where*.
2. **The wire.** Before a transaction reaches the ledger, a computer somewhere broadcasts it over the Bitcoin peer-to-peer network. That broadcast has an **IP address, a port and a timestamp**. Only someone who can see network traffic sees this layer, and NTRO is such an organisation.

Each layer alone is weak.
- **Ledger-only analysis** can group wallets that probably belong together, but it cannot tell you where they are operated from.
- **Network-only analysis** can see IPs, but it cannot tell you what the money did.

**Fused, they answer the questions that matter:** *which wallets belong to the same operator, where that operator is probably connecting from, how the money moved, where it was cashed out, and how sure we are of each of those statements.*

An analyst faced with bulk traffic data today hits three concrete problems:

1. **Volume without priority.** Millions of records and no ranked list of where to look first.
2. **Scores without reasons.** A black-box "risk score" cannot be acted on, defended, or corrected.
3. **Results without reproducibility.** A finding that another person cannot recompute from the same data is a lead at best, never evidence. The forensic literature is blunt about this: address clustering *generates leads; it is not evidence* (Iknaio, 2026; Müller et al., 2026).

## 1.2 What we are building

**An offline platform that turns bulk Bitcoin traffic records into a ranked list of explainable, reproducible investigative leads.**

Everything else in this document serves that sentence. The platform:

- **ingests** bulk traffic metadata in CSV, JSON or XML, including layouts it has never seen, by mapping columns instead of rejecting files;
- **enriches** every IP with country, network operator (ASN), and whether it is a Tor exit, a VPN or a hosting provider, using databases that ship *inside* the install;
- **builds one graph** linking IPs, transactions, addresses and inferred entities, where every link records *how it was inferred and how confident we are*;
- **correlates the wire with the ledger**. It works out which IP most probably originated each transaction and which wallets that IP most probably controls, and it says so with a calibrated probability, or says *"not observable"* when it cannot tell;
- **applies AI/ML, not just rules.** Seven small trained models cover mixing detection, change detection, peel-chain scoring, origin attribution, entity resolution, anomaly detection and lead ranking, plus a risk-propagation algorithm from known-bad wallets;
- **produces a ranked lead list** in which every lead has a confidence, a grade, the reasons behind it, the evidence graph that supports it, and what would have to change for it to go away;
- **presents it all in an analyst console**: triage queue, link-analysis canvas, actor dossiers, a world map of flows, and a *replay* that shows a transaction rippling across the network while the model's estimate of its origin converges;
- **exports case files** with a SHA-256 hash report and a tamper-evident audit trail, so a finding can be re-verified by someone else, years later, from the same data;
- **runs with the network cable unplugged**, on a Linux machine, from a single installer.

## 1.3 What it is not

Scope discipline is what makes this finishable in ten weeks by six people.

| It is not | Why |
|---|---|
| A live packet sniffer | The PS asks for **bulk metadata ingestion** (CSV/JSON/XML). Capturing traffic is the sensor's job, not ours. The design supports repeated batch ingestion ("monitoring mode") without pretending to be a capture appliance. |
| A Bitcoin node or block explorer | Offline means no node sync and no explorer APIs. Everything we know about transactions comes from the ingested records. |
| A multi-chain tool | Bitcoin only, as the PS says. The graph model does not preclude other UTXO chains later. |
| An identity resolver | We attribute wallets to **IPs, networks and operators-as-clusters**, never to named people. Naming people is lawful process (for example a notice to an exchange), not software. |
| A chatbot | No LLM in the core. Narratives come from deterministic templates filled from evidence. This keeps everything offline and removes any hallucination liability in forensic output. |
| A verdict machine | Leads, not convictions. Every output is phrased as a hypothesis with a confidence and its evidence. |
| Built on another blockchain | No Solana, no on-chain anchoring. Tamper evidence is a local hash chain. Writing investigation metadata to a public chain would leak that an investigation exists. |

## 1.4 How a dataset moves through it

```
   01 INGEST            02 NORMALISE &          03 BUILD THE            04 DETECT
   CSV · JSON · XML ──►   ENRICH            ──►    GRAPH           ──►    PATTERNS
   any column layout     units · time · IP       IPs · txs · wallets      mixing · peel chains
   mapping profiles      → country · ASN ·       · money flows            · laundering motifs
   reject report          Tor · VPN · hosting    · clusters               · anomalies
                                                                                 │
                                                                                 ▼
   08 CASE FILE    ◄──  07 TRIAGE &       ◄──  06 SCORE &          ◄──  05 CORRELATE
   evidence pack        INVESTIGATE             EXPLAIN                  WIRE ⇄ LEDGER
   SHA-256 report       queue · canvas ·        risk from known-bad      which IP sent it ·
   audit chain          dossiers · replay       · ranked leads ·         which wallets it
   MISP · STIX · PDF    · analyst feedback      reasons · grades         controls · who is who
```

Three details are easy to miss and matter a great deal:

**A run is frozen once it finishes.** Every analysis run records exactly which input files (by hash), which settings and which model versions it used, and produces a *result digest*. Running it again produces the same digest. That is what turns an output into something another person can check.

**The origin of a transaction is not always knowable, and the system says so.** If the computer that created a transaction was never connected to any observation point, no algorithm can find it. The model outputs an explicit *"not observable"* probability instead of confidently guessing. An honest *"we can't tell"* beats a confident wrong IP.

**Exchanges are where investigations end, not where criminals live.** When illicit money lands at an exchange deposit address, that address belongs to the exchange, but the *account* belongs to the criminal. The platform treats these as a separate, highly actionable lead type (**CASHOUT**): *"send a lawful notice to this service about this deposit address."* This is the most useful thing an investigator can receive.

## 1.5 The five things the platform will not do

These are enforced by code and tests. They are not guidelines.

| | The rule | How it is enforced |
|---|---|---|
| **1** | **It never talks to the internet.** | An in-process guard blocks every outbound connection. The application tier sits on a Docker network with no route out. CI runs the full pipeline in a container with networking disabled. |
| **2** | **It never shows a score without reasons.** | A lead cannot be published without a calibrated probability, a grade, at least one reason and at least one supporting evidence family. The database refuses it otherwise. |
| **3** | **It never states a link without saying how it knows.** | Every inferred edge (IP→transaction, wallet→wallet, entity→entity) carries its method, confidence, evidence references, model version and run ID. |
| **4** | **It never produces a result it cannot reproduce.** | A run manifest plus a determinism test. The same inputs, settings and models must give the same result digest. |
| **5** | **It never lets mixing transactions merge unrelated people.** | Transactions the CoinJoin model flags are excluded from wallet clustering, and oversized clusters are automatically inspected and split. |

## 1.6 The seven modules

| | Module | Its one job |
|---|---|---|
| **M1** | **Ingest** | Take any bulk file (CSV/JSON/XML), map its columns, validate every row, report what was rejected and why, and profile the dataset in under a minute ("Dataset X-ray"). |
| **M2** | **Engine** | The headless analytics pipeline: normalise → enrich → graph → detect → correlate → resolve → score → explain → publish. It also runs as a command-line tool. |
| **M3** | **Triage** | The ranked lead queue: grades, confidence, priority, filters, keyboard-first review, confirm/dismiss feedback that retrains the ranker. |
| **M4** | **Investigate** | The link-analysis canvas, actor dossiers, the wire ⇄ ledger replay, the flow map, follow-the-money views and path-finding between any two nodes. |
| **M5** | **Cases & Evidence** | Case workspaces, notes, a hash-chained audit log, evidence-pack export with hash report, independent verification, and MISP/STIX/GraphML/i2 exports. |
| **M6** | **Lab** | The synthetic-world generator (Scenario Studio), the evaluation and red-team reports, the sensor-coverage planner, and the Academy (training challenges scored against ground truth). |
| **M7** | **Govern** | Model registry and model cards, drift monitoring, shadow evaluation and promotion, users and roles, settings, audit verification, system health. |

**The centrepiece is the correlation inside M2, surfaced in M4.** It is the only part of this PS that a generic crypto-AML project cannot fake: *"correlates network-layer (IP/port/timing) observations with blockchain-layer (wallet/TXID/amount) data."* Every other module either feeds it or makes its output usable.

## 1.7 What "done" means

The definition of done is NTRO's own text:

> *"Design and build a complete system (offline) that ingests bulk Bitcoin transaction/network metadata (in CSV/JSON/XML), correlates network-layer (IP/port/timing) observations with blockchain-layer (wallet/TXID/amount) data, and applies AI/ML to detect anomalies, cluster entities, and generate prioritized, explainable investigative leads."*

Plus five challenge objectives, four suggested AI/ML focus areas, the dataset parameters, and four expected deliverables. §2.2 maps **every clause** to a feature, a screen, an endpoint and an automated test. If any clause cannot be demonstrated live, the product is not finished.

## 1.8 What NTRO and the judges receive

- **The air-gapped bundle.** One archive: images, models, reference data, sample datasets, installer, and a `SHA256SUMS` file. On a fresh Linux machine it goes from zero to the hero demo in under fifteen minutes, with networking off.
- **The code repository**, with CI results, tests and releases visible.
- **The technical write-up** the PS asks for: approach, model choice, explainability method. Plus a model card per model.
- **The dashboard**, live in the air-gapped build, and as a public showroom on synthetic data.
- **The evaluation report.** Every metric on held-out synthetic worlds and a red-team robustness report, regenerated by CI on every change.
- **A 3-minute video** of the full workflow running offline.

## 1.9 One codebase, two targets

The PS says **offline**. Judges need **links**. Both are satisfied by building one codebase that ships two ways:

| | **Air-gapped (the product)** | **Cloud showroom (the demo)** |
|---|---|---|
| Who it is for | NTRO, and the finale evaluation | Judges, mentors, anyone with the link |
| Where | Any Linux machine, `docker compose`, no network | Web on **Vercel**, API on **Render** |
| Data | Anything ingested | **Synthetic only**, a pre-built hero world plus capped, auto-deleted uploads |
| Database | PostgreSQL | SQLite, reset nightly |
| Images | `sutradhar-api`, `sutradhar-web` | **The same images**, plus a baked-in demo world |

The line for the pitch: *"The same images run in our cloud sandbox and fully air-gapped. The link is for you; the bundle is for NTRO."*

---


# PART 2 — PRODUCT DEFINITION & REQUIREMENT TRACEABILITY

## 2.1 The requirement numbering scheme

Every requirement carries a stable ID. This is not bureaucracy. It is how we prove to judges that *every* clause of the PS is built and tested. It is also how an AI coding agent is told exactly what to build without inventing scope.

| Prefix | Scope | Example |
|---|---|---|
| `R-PS-nn` | A clause of the NTRO problem statement | `R-PS-03` correlate network with blockchain layer |
| `R-ING-nnn` | M1 Ingest | `R-ING-007` XML parsed with external entities disabled |
| `R-ENG-nnn` | M2 Engine | `R-ENG-031` CoinJoin transactions excluded from CIOH merges |
| `R-TRI-nnn` | M3 Triage | `R-TRI-004` keyboard triage (J/K/C/D) |
| `R-INV-nnn` | M4 Investigate | `R-INV-012` path finder between two nodes |
| `R-CAS-nnn` | M5 Cases & Evidence | `R-CAS-009` evidence pack verification |
| `R-LAB-nnn` | M6 Lab | `R-LAB-003` adversary knobs in the generator |
| `R-GOV-nnn` | M7 Govern | `R-GOV-005` model promotion gate |
| `R-PLT-nnn` | Platform (deploy, CI, offline) | `R-PLT-002` air-gapped install under 15 minutes |
| `R-SEC-nnn` | Security | `R-SEC-011` CSV formula-injection neutralised |

Each requirement row in `docs/requirements.csv` (format in §17.4) records the statement, module, screen, endpoint, database objects, proving test ID, phase and status. **No requirement is marked done without a passing test recorded against it.**

## 2.2 The acceptance test — the PS, clause by clause

This table is the definition of done. Each row is demonstrated live at the finale and proven by an automated test in CI.

| ID | PS clause (verbatim or near-verbatim) | How we satisfy it | Where you see it | Proving test | Phase |
|---|---|---|---|---|---|
| **R-PS-01** | "design and build a complete system **(offline)**" | Air-gapped compose stack. In-process network guard. The application tier sits on an internal-only Docker network. | System page shows **AIR-GAPPED ✓**; `sutradhar selfcheck` | `test_offline_pipeline_no_network` (container with `--network none`), `test_web_makes_no_external_requests` | P0, P8 |
| **R-PS-02** | "ingests bulk Bitcoin transaction/network metadata (in **CSV/JSON/XML**)" | Streaming readers for CSV/TSV, JSON array, NDJSON and XML. Mapping profiles. Auto-mapper for unknown layouts. | Ingest → upload → mapping wizard → X-ray | `test_three_formats_same_digest` (identical normalised digest from CSV, JSON and XML of one world) | P2 |
| **R-PS-03** | "**correlates** network-layer (IP/port/timing) observations with blockchain-layer (wallet/TXID/amount) data" | Origin attribution (`origin_ranker`), sessions, IP→address/entity control (noisy-OR), co-origin linking, clock-skew correction | Lead → **Network** tab · Replay · IP dossier | `test_origin_beats_first_spy` (held-out worlds) and `test_control_links_calibrated` | P4 |
| **R-PS-04** | "applies AI/ML to **detect anomalies, cluster entities**, and generate **prioritized, explainable investigative leads**" | Seven models plus risk propagation. Ranked leads with calibrated probability, grade and reasons | Triage queue | `test_every_lead_has_reason_grade_calibrated_p` | P3–P5 |
| **R-PS-05** | "Ingest & parse … (timestamp, src/dst IP & port, TXID, input/output wallet addresses, amounts, **fee, script type**)" | Data contract v1 (§4.2). Fee computed when absent. Script type inferred from address format when absent. | X-ray field coverage panel | `test_contract_fields_parsed`, `test_fee_computed_when_missing`, `test_script_type_inference` | P2 |
| **R-PS-06** | "Build an **entity/transaction graph linking IPs, wallets, and transactions**" | Graph model (§4.7): IP, TX, ADDRESS, ENTITY, ACTOR, SENSOR, ASN and COUNTRY nodes; 16 edge types, each with an evidence envelope | Investigate canvas | `test_graph_has_all_node_types`, `test_every_edge_has_evidence_envelope` | P3 |
| **R-PS-07** | "Implement AI/ML detection use case with a **working model — not just rules**" | Trained LightGBM models with published metrics against rule baselines (first-spy, fixed-threshold CoinJoin rules, plain CIOH) | Govern → Models → model card | `test_models_beat_rule_baselines` (eval gate) | P3–P5 |
| **R-PS-08** | "Generate a **ranked, explainable alert list** (why a wallet/transaction was flagged, **with a confidence score**)" | Leads of types ACTOR/CASHOUT/CHAIN/TX/IP. Priority ranking. TreeSHAP reasons. Counterfactuals. Isotonic-calibrated confidence. | Triage → lead → **Why** tab | `test_calibration_ece_below_target`, `test_reasons_match_top_contributions` | P5 |
| **R-PS-09** | "Present findings via a simple **dashboard or link-analysis visualization**" | Analyst console: overview, triage, canvas, dossiers, geo map, Sankey, replay | The whole web app | Playwright `e2e_analyst_journey` | P6 |
| **R-PS-10** | Focus: **Entity clustering** — "common-input-ownership + **graph embeddings**" | CIOH (union-find, CoinJoin-gated) plus randomized-SVD embeddings plus the `er_pair_clf` entity-resolution model plus analyst-approved merge suggestions | Actor dossier → **Membership** tab (each member with its evidence) | `test_cioh_excludes_coinjoin`, `test_er_improves_per_wallet_recall` | P3–P4 |
| **R-PS-11** | Focus: **Anomaly detection** — "statistically unusual transactions/flows" | Isolation Forest at transaction and actor level, as rank-normalised scores. Feeds the ranker and appears as its own evidence family (ANOM). | Lead → Why → ANOM reasons; TX page | `test_anomaly_scores_injected_outliers_high` | P5 |
| **R-PS-12** | Focus: **Peeling-chain / mixing detection** — "peeling chains, CoinJoin-like structures" | `coinjoin_clf` (Whirlpool-, Wasabi-, JoinMarket-like and generic equal-output structures) and a peel-chain traversal scored by `peel_scorer` | CHAIN leads; canvas "chain" layout | `test_peel_chain_recall_5plus_hops`, `test_coinjoin_f1` | P3 |
| **R-PS-13** | Focus: **Risk scoring** — "propagate risk scores from seed illicit wallets via algorithms" | Watchlist seeds → haircut taint with hop decay and service stopping, personalized PageRank, and k-best paths as explanations. Victims are separated from perpetrators. | Lead → **Path to seed** tab | `test_taint_stops_at_services`, `test_victims_not_flagged_as_perpetrators` | P5 |
| **R-PS-14** | Dataset: "**synthetic** dataset modelled on real Bitcoin P2P/transaction fields" | In-house world generator (Part 5): UTXO economy plus P2P propagation plus sensors plus ground truth | Lab → Scenario Studio | `test_generator_deterministic`, `realism_report` thresholds | P1 |
| **R-PS-15** | Dataset: minimum fields "timestamp, src_ip, dst_ip, src_port, dst_port, txid, input_addresses[], output_addresses[], input_amounts[], output_amounts[], geo_country/asn" | Generator exports exactly these (plus optional extras). Ingest requires them for full capability and degrades gracefully without the network fields. | X-ray → capability report | `test_generator_exports_minimum_fields`, `test_chain_only_mode` | P1–P2 |
| **R-PS-16** | Dataset: "**integrate open source downloadable Geo IP database**" | DB-IP Lite (CC BY 4.0) country/city/ASN `.mmdb` bundled offline. IPinfo Lite optional. Every value tagged with source and as-of date. | IP dossier → enrichment panel with source and date | `test_geoip_offline_lookup`, `test_enrichment_provenance_present` | P2 |
| **R-PS-17** | Deliverable: "**Workable complete offline solution for linux platform**" | Air-gapped bundle plus `install.sh` plus `selfcheck.sh` | Release asset `sutradhar-airgap-<ver>-linux-amd64.tar.zst` | `release_bundle_smoke` job (fresh VM, no network) | P8 |
| **R-PS-18** | Deliverable: "Working prototype (**code repo**) with ingestion, correlation, and AI/ML model" | Monorepo with CI, tests, releases | GitHub repository | CI green on the `main` branch | P0→P8 |
| **R-PS-19** | Deliverable: "Short **technical write-up**: approach, model choice, and explainability method" | `docs/technical-writeup.md`, rendered to PDF and on the docs site, plus one model card per model | Docs site → Write-up | `docs_build` job; write-up checklist in §15 P8.6 | P8 |
| **R-PS-20** | Deliverable: "Dashboard/visualization showing **flagged entities and evidence for each flag**" | Lead detail: Summary, Why, Evidence graph, Network, Path to seed, Counterfactual, Timeline | Triage → any lead | `e2e_lead_evidence_tabs_render` | P5–P6 |

## 2.3 The people who use it, and what each one opens

### Role — Analyst
The default user. Their day is the **triage queue**. They open a lead, read *why*, pivot into the canvas, check the network attribution, then confirm, dismiss (with a reason) or escalate. They create cases, add leads and notes, and export evidence packs for their own cases. Their feedback is training data (§7.7).

### Role — Lead analyst
Everything an analyst does, plus:
- assigning leads;
- **accepting or rejecting entity-merge suggestions**, which become analyst assertions with provenance;
- closing cases;
- approving evidence-pack exports on escalated cases;
- managing watchlists (seed wallets and IPs).

### Role — Administrator
Users and roles, settings, reference-data updates (GeoIP, Tor and VPN snapshots), **model promotion**, Lab evaluations, system health. The administrator cannot edit or delete audit entries. Nobody can.

### Role — Auditor
Read-only access to everything, plus **audit-chain verification** and **evidence-pack verification**. This is the role you hand to an oversight body. It exists because an intelligence tool without an independent read-only audit role is a tool nobody should trust.

### Role — Demo visitor *(cloud showroom only)*
Analyst-equivalent inside the synthetic demo world. Uploads are capped and auto-deleted. No Govern access except read-only model cards. The judge who opens the link is this role. One click on "Enter demo", no sign-up.

## 2.4 The permission model

Roles are fixed (five) in v1. `[DECISION]`: a dynamic permission builder adds complexity no judge will reward. The matrix is data (`sutradhar_api/auth/permissions.py`), and one helper `require(action)` is the only way an endpoint checks it. `test_every_mutating_endpoint_declares_permission` fails CI if an endpoint forgets.

| Action | Analyst | Lead | Admin | Auditor | Demo |
|---|:-:|:-:|:-:|:-:|:-:|
| View runs, leads, graph, dossiers | ✓ | ✓ | ✓ | ✓ | ✓ (demo world) |
| Triage: status, feedback, notes | ✓ | ✓ | – | – | ✓ (ephemeral) |
| Assign leads | – | ✓ | ✓ | – | – |
| Create/edit own cases | ✓ | ✓ | – | – | ✓ (ephemeral) |
| Close cases · approve escalated exports | – | ✓ | – | – | – |
| Export evidence pack (own case) | ✓ | ✓ | – | – | ✓ (watermarked) |
| **Verify** evidence pack | ✓ | ✓ | ✓ | ✓ | ✓ |
| Accept/reject merge suggestions | – | ✓ | – | – | – |
| Manage watchlists | – | ✓ | ✓ | – | – |
| Upload dataset · start run | ✓ | ✓ | ✓ | – | ✓ (≤25 MB, TTL) |
| Lab: generate scenario · run evaluation | – | ✓ | ✓ | – | ✓ (preset scenarios only) |
| Academy: attempt challenges | ✓ | ✓ | ✓ | ✓ | ✓ |
| Promote / roll back a model | – | – | ✓ | – | – |
| Users, roles, settings, reference data | – | – | ✓ | – | – |
| View audit log · **verify chain** | – | ✓ | ✓ | ✓ | – |
| Reset demo world | – | – | ✓ (demo) | – | – |

## 2.5 Leads, precisely specified

### 2.5.1 Lead types

| Type | Subject | Raised when | Why an investigator cares |
|---|---|---|---|
| **ACTOR** | A resolved actor: one or more wallet clusters, their attributed IPs and sessions | `lead_ranker` p ≥ grade-C floor | "This is probably one operator. Here is what they did, and from where." |
| **CASHOUT** | A deposit address **at a detected service** (exchange, OTC, gambling) | Taint from seeds ≥ threshold reaches a service-owned address | **Most actionable output.** A lawful notice to that service about that deposit address can produce an identity. |
| **CHAIN** | A peel chain or laundering sequence (ordered list of transactions) | `peel_scorer` or a motif detector over threshold | Shows the *method*, and often ends at a CASHOUT. |
| **TX** | A single transaction | CoinJoin entry/exit from tainted funds, an anomalous transaction, or a watchlist hit | Point evidence for an ACTOR or CHAIN. |
| **IP** | A network endpoint | Attributed as origin for illicit-scored activity with p ≥ threshold | Network-side lead. Shows ASN, country, Tor/VPN/hosting, sessions, timezone. |

### 2.5.2 Evidence families

A lead's strength comes from **independent** kinds of evidence agreeing. There are five families, and the grade counts how many of them support the lead.

| Family | Code | What counts | Colour token |
|---|---|---|---|
| Network attribution | **NET** | Origin/control/co-origin evidence from IP, port and timing | `--fam-net` cyan |
| On-chain pattern | **FLOW** | CoinJoin, peel chain, laundering motifs, clustering | `--fam-flow` violet |
| Risk path | **TAINT** | Haircut taint, PPR and paths from watchlist seeds | `--fam-taint` red |
| Statistical anomaly | **ANOM** | Isolation-Forest outliers at transaction or actor level | `--fam-anom` amber |
| Behavioural fingerprint | **BEHAV** | Timezone profile, anonymising-infrastructure use, fee/rounding habits | `--fam-behav` green |

A family **supports** a lead when either its summed TreeSHAP contribution to the ranker's log-odds is ≥ `+0.05` `[DEFAULT]`, or a detector in that family fired on the lead's subject.

### 2.5.3 Grades, priority and status

**Grade** (settings §17.3):
- **A:** p ≥ 0.80 **and** ≥ 3 supporting families.
- **B:** p ≥ 0.60 **and** ≥ 2 families.
- **C:** p ≥ 0.40.
- **Below C:** not a lead. Still searchable, never queued.

The grade badge always shows the family icons next to it, so the grade is never shown without its evidence (invariant **I17**).

**Priority** is what the queue sorts by. It deliberately differs from probability: a certain lead about 0.001 BTC matters less than a likely lead about 20 BTC that happened yesterday.

```
priority = p_calibrated
         × (1 + log10(1 + 10 × value_at_risk_btc))
         × 0.5 ^ (days_since_last_activity / 14)
         × (1 + 0.25 × actionable)
actionable = 1 if (lead has a CASHOUT at a known service) or (an attributed origin IP with p ≥ 0.6 that is not Tor/VPN) else 0
```
All four factors and weights are settings `[DEFAULT]`. The lead detail shows the priority decomposed into those factors, so nobody has to trust a number they cannot read.

**Status lifecycle:**
```
            ┌──────────── snooze(until) ─────────────┐
            ▼                                         │
  NEW ──► IN_REVIEW ──► ESCALATED ──► CONFIRMED       │
   │          │             │                         │
   │          └──► DISMISSED (reason required) ◄──────┘
   └─────────────────► SNOOZED ──(until reached)──► NEW
  CONFIRMED / DISMISSED ──reopen (lead+)──► IN_REVIEW
```
- **Dismissal requires a reason code:** `benign_service`, `victim`, `duplicate`, `insufficient_evidence`, `known_false_positive_pattern` or `other`+text. The reason codes feed retraining (§7.7).
- **Status is workflow state, stored in the app DB** keyed by `(run_id, lead_key)`. The lead's *content* (score, reasons, evidence) is immutable run output.
- **Status survives re-runs.** When a new run publishes a lead with the same `lead_key` (a stable hash of type plus subject), its state is carried forward and marked **"changed since last review"** if its grade or priority moved.

## 2.6 The run lifecycle

```
DATASET:  UPLOADED ──► MAPPED ──► VALIDATED ──► NORMALISED ──► (READY)
                          │            │
                          │            └── reject report (row-level, downloadable)
                          └── mapping profile (auto-proposed → confirmed)

RUN:      QUEUED ──► RUNNING[E01…E19] ──► COMPLETED ──► PUBLISHED
                          │                     │
                          └──► FAILED (stage, error, resumable from last completed stage)
                                                └── manifest.json + result_digest (immutable)

MONITORING (optional series):
  batch n arrives ──► dataset vn ──► run over window W ──► diff vs run n-1
                                                          ├── NEW leads          (badge)
                                                          ├── CHANGED leads      (badge)
                                                          └── WATCHLIST HITS     (rule-labelled, instant)
```

`[DECISION]` **Runs are full recomputations over a window, not incremental graph updates.**
- **Why:** incremental clustering and propagation invite subtle drift that breaks the reproducibility invariant (I4).
- **Is it fast enough?** At our scale (≤ a few million observations per window) a full run takes minutes (§14.3 targets).
- **What the analyst sees:** new and changed leads, marked through a diff against the previous run.

## 2.7 Merge suggestions — the human in the loop for entity resolution

Common-input clustering is a lead generator with published failure modes (per-wallet precision 0.36 and recall 0.44 on real EU ground truth; Müller et al. 2026). So the system never silently merges on weak evidence:

| `er_pair_clf` probability | What happens |
|---|---|
| ≥ 0.90 and neither side CoinJoin-contaminated | Merged automatically into one **actor**. The merge edge is recorded with method `er_model`. |
| 0.60 – 0.90 | Raised as a **merge suggestion** in the actor dossier and the Lead-analyst queue. |
| < 0.60 | Not shown. Kept in the run store for audit. |

Accepted suggestions become **analyst assertions**: rows with `method = analyst_assertion`, the user, the time and the reason. They are applied to the next run as constraints. A rejected suggestion is remembered, so the same pair is never proposed twice. The whole loop is audited.

---


# PART 3 — SYSTEM ARCHITECTURE

## 3.1 The one-page architecture

*Everything in the system on one page. If you read only one diagram, read this one.*

```
╔═══════════════════════════════════════════════════════════════════════════════════════════════════╗
║  PEOPLE                                                                                           ║
╠════════════════╤════════════════╤════════════════╤════════════════╤═══════════════════════════════╣
║  Analyst       │  Lead analyst  │  Administrator │  Auditor       │  Judge / mentor               ║
║  triage, cases │  merges, close │  models, users │  read + verify │  public link · synthetic only ║
╚═══════╤════════╧═══════╤════════╧═══════╤════════╧═══════╤════════╧══════════════╤════════════════╝
        └────────────────┴────────┬───────┴────────────────┘                       │
                                  │                                                │
                     ┌────────────▼─────────────┐                    ┌─────────────▼─────────────┐
                     │  ANALYST CONSOLE (SPA)   │                    │  VERCEL                    │
                     │  React 19 · Vite · TS    │   same build ────► │  web app (same SPA build)  │
                     │  TanStack Router/Query   │                    │  site: landing · docs ·    │
                     │  Cytoscape · Sigma ·     │                    │  metrics (Astro Starlight) │
                     │  deck.gl · ECharts       │                    └─────────────┬─────────────┘
                     └────────────┬─────────────┘                                  │ HTTPS · CORS
                                  │ same-origin /api                               │ bearer JWT
 ═════════════ AIR-GAPPED LINUX HOST (the product) ═════════════   ═════ RENDER · Singapore (demo) ════
                     ┌────────────▼─────────────┐                  ┌───────────────▼──────────────┐
                     │ CADDY  (edge network)    │                  │ sutradhar-api-demo  (image)  │
                     │ static SPA + /api proxy  │                  │ APP_MODE=demo · SQLite       │
                     │ CSP · no ACME · no admin │                  │ embedded worker · hero world │
                     └────────────┬─────────────┘                  │ nightly reset · upload TTL   │
          internal-only network   │  (no default route)            └──────────────────────────────┘
   ┌──────────────────────────────▼───────────────────────────────────────────────────┐
   │  SUTRADHAR API  — FastAPI · uvicorn · modular monolith                            │
   │  ┌─────────────────────────────────────────────────────────────────────────────┐ │
   │  │ API LAYER      routers · JWT auth · require(action) · cursor pagination · SSE │ │
   │  ├─────────────────────────────────────────────────────────────────────────────┤ │
   │  │ SERVICE LAYER  datasets · runs · leads · cases · evidence · lab · govern     │ │
   │  │                audit.append() in the SAME transaction as every mutation      │ │
   │  ├─────────────────────────────────────────────────────────────────────────────┤ │
   │  │ READ MODELS    run-store readers (DuckDB, read-only) · graph & path queries  │ │
   │  └─────────────────────────────────────────────────────────────────────────────┘ │
   │  OFFLINE GUARD  every socket.connect → loopback / RFC1918 compose ranges only     │
   └────────┬───────────────────────────────┬──────────────────────────┬──────────────┘
            │ SQLAlchemy                    │ jobs (FOR UPDATE           │ files
            ▼                               ▼  SKIP LOCKED)              ▼
   ┌──────────────────┐        ┌───────────────────────────────┐   ┌───────────────────────────┐
   │ POSTGRES 17      │◄──────►│ WORKER  (same image)          │──►│ /data (volume)             │
   │ the APP DB       │        │ one subprocess per job:       │   │  datasets/<id>/raw/        │
   │ users · sessions │        │  • ingest I01–I06             │   │  datasets/<id>/dataset.duckdb│
   │ datasets · runs  │        │  • ENGINE E01 → E19           │   │  runs/<id>/run.duckdb (RO) │
   │ jobs · leads     │        │  • Lab: generator · evals     │   │  exports/<id>.zip          │
   │ lead_state       │        │  • exports · verification     │   │ /models   (RO, versioned)  │
   │ cases · feedback │        │  • retrain (shadow)           │   │ /refdata  (RO, dated)      │
   │ audit_log ⛓      │        └───────────────────────────────┘   └───────────────────────────┘
   └──────────────────┘
   ⛓ = append-only, SHA-256 hash-chained, verified by /api/v1/audit/verify
```

**Read the diagram as five bands, top to bottom:**
1. **People:** four internal roles plus the public demo visitor.
2. **Clients:** one SPA build, served by Caddy in the air-gapped host and by Vercel in the showroom. The landing, docs and metrics site is a separate static Astro project, also on Vercel.
3. **Edge and application:** Caddy is the only container with a route to the host. The API is a modular monolith whose service layer writes an audit entry in the same transaction as every change.
4. **Compute:** a worker process (same image, different command) runs every heavy job in a fresh subprocess. That includes ingestion, the 19-stage engine, the generator, evaluations, exports and verification.
5. **State:** Postgres holds *workflow* state (who did what, lead status, cases, audit). Immutable per-run DuckDB files hold *analytics and evidence*. Models and reference data are mounted read-only and versioned.

## 3.2 Why a modular monolith plus a worker, and not anything else

`[DECISION]` One API process and one worker process, from one Python codebase and one image. Internal boundaries are enforced by tests.

| Option | Why not |
|---|---|
| Microservices | Six students, ten weeks, one deployment target that must run offline on a laptop. The distributed-systems tax (service discovery, network partitions, tracing) buys nothing, and every extra container is one more thing to break during an air-gapped install. |
| Serverless (Vercel/Lambda functions) | The engine holds a graph in memory and runs for minutes. Vercel Hobby functions cap at 2 GB and 300 s per request and include only 4 active CPU-hours a month. And serverless cannot be the air-gapped product anyway. |
| Django + DRF (what Audire uses) | Django earns its place in an ERP (admin, auth, ORM migrations for a hundred tables). Here the API is thin and the engine is the product. FastAPI gives typed request/response models, first-class async SSE and an OpenAPI schema we generate the TypeScript client from, with far less ceremony. |
| Streamlit / Gradio dashboard | Fast to start, but it looks like every other hackathon entry. It cannot do keyboard-first triage, a 2,000-node interactive canvas or a replay animation, and its server model fights our offline and RBAC requirements. It is what the other 499 teams will build. |
| Neo4j-centred design | A second heavyweight server in the air-gapped bundle, a JVM, and a query language the team would have to learn. Our graph queries are neighbourhood expansion and k-best paths. DuckDB tables with indexes plus igraph in the worker do both, and the run file doubles as the evidence artefact. |
| All-TypeScript (Node API) | The engine's ecosystem (LightGBM, scikit-learn, igraph, SciPy, DuckDB, Polars) is Python. Splitting languages across the API/engine boundary would duplicate the data contract. |

**The monolith is not a mud ball.** Boundaries are enforced mechanically by `import-linter` (§3.3). Any cross-module call above the schema layer goes through a declared interface.

## 3.3 Packages, layers and the import contract

```
sih26146/
├── apps/
│   ├── api/                 sutradhar_api     FastAPI app: routers, services, auth, jobs, SSE, read models
│   ├── web/                 @sutradhar/web    React SPA (analyst console)
│   └── site/                @sutradhar/site   Astro Starlight: landing, docs, metrics page
├── packages/
│   ├── schemas/             sutradhar_schemas Pydantic models: data contract, run manifest, lead, evidence envelope
│   ├── engine/              sutradhar_engine  ingest I01–I06, pipeline E01–E19, models, explain, evidence, digests
│   ├── generator/           sutradhar_gen     synthetic world, P2P sim, observation models, exporters, scenarios
│   ├── evals/               sutradhar_evals   truth readers, metrics, reports, red-team sweeps, planner, academy scoring
│   ├── cli/                 sutradhar_cli     `sutradhar` command (Typer): gen · ingest · run · eval · export · verify · serve · worker
│   ├── plugins/             sutradhar_plugins built-in detector plugins (peel, coinjoin, motifs) on the public SDK
│   ├── ts-client/           @sutradhar/client TypeScript client generated from OpenAPI
│   └── tokens/              @sutradhar/tokens design tokens (CSS variables) shared by web and site
├── models/                  versioned model artefacts + model cards (small; committed)
├── deploy/                  docker/ · compose/ · airgap/ · render/ · caddy/
├── docs/                    ADRs · INVARIANTS.md · requirements.csv · technical-writeup.md · runbooks
└── .github/workflows/       ci · eval · images · deploy · release · nightly
```

**The import contract** (`.importlinter`, checked in CI):

```
                sutradhar_cli
                      │
          ┌───────────┴────────────┐
          ▼                        ▼
   sutradhar_api            sutradhar_evals ──────────────┐
          │                        │                       │ (evals may read truth;
          ├────────────┬───────────┤                       │  nothing else may)
          ▼            ▼           ▼                       ▼
  sutradhar_engine   sutradhar_gen            truth files (generator output)
          │            │
          └─────┬──────┘
                ▼
        sutradhar_schemas
```

- `sutradhar_engine` **must not** import `sutradhar_gen`, `sutradhar_evals` or `sutradhar_api`. The engine cannot see ground truth even by accident (invariant **I7**).
- `sutradhar_gen` **must not** import `sutradhar_engine`. The world is generated without knowing how it will be analysed, so there is no teaching to the test.
- `sutradhar_api` may import the engine (read models, job entry points), the generator (Lab jobs) and evals (Lab reports). Inference code paths never take truth as input.
- Plugins import only `sutradhar_engine.sdk` (the public detector API) and `sutradhar_schemas`.

**Four layers inside the API** (same discipline as a good Django app):

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 1. API LAYER       routers/*.py — HTTP, auth, require(action), (de)serialisation  │
│    FORBIDDEN: business rules, opening transactions, touching DuckDB directly      │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 2. SERVICE LAYER   services/*.py — the only place a DB transaction opens          │
│    Every mutation calls audit.append(...) inside the same transaction.            │
│    Enqueues jobs; never runs heavy work inline.                                    │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 3. READ MODELS     readers/*.py — read-only DuckDB connections to run.duckdb,     │
│    graph neighbourhood / path queries, pagination cursors                          │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 4. DOMAIN          models/*.py (SQLAlchemy) + DB constraints/triggers.            │
│    Invariants that must hold even if a service has a bug live HERE.               │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 3.4 The engine pipeline

The engine is a deterministic DAG of stages. Each stage reads earlier tables from the run store, writes its own tables, and logs timings and row counts. On failure it can be resumed from the last completed stage.

**Ingestion (per dataset, before any run), in M1:**

| Stage | Name | Does | Output |
|---|---|---|---|
| I01 | `read` | Streaming readers: CSV/TSV, JSON array, NDJSON, XML (safe parser) | record batches |
| I02 | `map` | Apply mapping profile (auto-proposed, analyst-confirmed) | canonical batches |
| I03 | `normalise` | Units → satoshis, time → UTC µs, arrays aligned, IPs canonicalised, script type inferred | `obs`, `tx`, `txin`, `txout` |
| I04 | `validate` | Rules V01–V20 (§4.5) | `rejects` + reasons |
| I05 | `reconcile` | Deduplicate rows, detect conflicting content for the same txid | quarantine list |
| I06 | `profile` | Capability detection and Dataset X-ray | `xray.json` |

**Engine (per run), in M2:**

| Stage | Name | Does | Model / algorithm | Evidence family |
|---|---|---|---|---|
| E01 | `load` | Attach dataset (read-only), snapshot capability profile, detect observation model | rules | – |
| E02 | `enrich` | IP → country/ASN/Tor/VPN/hosting/bogon, listener vs client role, sensor identification | DB-IP `.mmdb` and lists | NET / BEHAV |
| E03 | `flows` | Rebuild tx→tx money flow via prevouts or **(address, amount) matching** | exact matching | FLOW |
| E04 | `coinjoin` | Score every transaction for mixing structure | `coinjoin_clf` | FLOW |
| E05 | `cluster` | Common-input-ownership clustering **excluding CoinJoins**; inspect and split mega-clusters | union-find (SciPy components) | FLOW |
| E06 | `change` | Identify change outputs; merge only on very high confidence | `change_clf` | FLOW |
| E07 | `peel` | Follow change outputs forward; score candidate chains | traversal + `peel_scorer` | FLOW |
| E08 | `motifs` | Fan-in/out, scatter-gather, gather-scatter, cycles, stacks (detector plugins) | windowed motif counts | FLOW |
| E09 | `timing` | Per-sensor clock-skew correction, TCP-session reconstruction | robust median offsets | NET |
| E10 | `origin` | Probability each candidate IP originated each transaction, plus P(not observable) | `origin_ranker` | NET |
| E11 | `control` | IP→address/entity control (noisy-OR), IP crowdedness, co-origin edges | aggregation | NET |
| E12 | `embed` | Entity embeddings from the flow graph | randomized SVD | FLOW |
| E13 | `resolve` | Merge entities into **actors**, raise merge suggestions, apply analyst assertions | `er_pair_clf` | NET / BEHAV |
| E14 | `services` | Detect services (exchange, mixer, gambling, pool); separate victims from perpetrators | service score | – |
| E15 | `risk` | Watchlist seeds → haircut taint (decay, service stop), PPR, k-best paths | propagation | TAINT |
| E16 | `anomaly` | Transaction- and actor-level outliers | `anomaly_iforest` | ANOM |
| E17 | `rank` | Actor features → calibrated probability → grade → priority → leads of all five types | `lead_ranker` + isotonic | all |
| E18 | `explain` | TreeSHAP reasons, counterfactuals, evidence subgraphs, timezone and behaviour summaries | `pred_contrib` | all |
| E19 | `publish` | Finalise the run store (read-only), result digest, manifest, publish leads to app DB, diff against previous run | digest | – |

Part 6 specifies every stage, and Part 7 specifies every model.

## 3.5 Deployment topologies

### 3.5.1 Air-gapped (the product)

```
                    ┌────────────────────────────────────────────────────────────────┐
  analyst browser ─►│  Linux host · 8 vCPU / 16 GB / 100 GB SSD (reference)          │
  http://127.0.0.1  │  Docker Engine + Compose v2 · NO network connection required   │
    :8080           │                                                                │
                    │  network "edge" (bridge)        network "app" (internal: true) │
                    │  ┌───────────┐                  ┌───────────┐ ┌─────────────┐  │
                    │  │  web      │── /api/* ───────►│  api      │ │  worker     │  │
                    │  │  Caddy +  │                  │  :8000    │ │  --conc 2   │  │
                    │  │  SPA dist │                  └─────┬─────┘ └──────┬──────┘  │
                    │  └───────────┘                        └──────┬───────┘         │
                    │   published: 127.0.0.1:8080 only             ▼                 │
                    │                                       ┌──────────────┐         │
                    │                                       │ db           │         │
                    │                                       │ postgres:17  │         │
                    │                                       └──────────────┘         │
                    │  volumes: pgdata · data · models (ro) · refdata (ro)            │
                    └────────────────────────────────────────────────────────────────┘
```

- **Only `web` touches the host.** It publishes to `127.0.0.1:8080` by default, and to the LAN only if `BIND=0.0.0.0` is set deliberately.
- **`api`, `worker` and `db` live only on an `internal: true` network,** so they have no default route even if the host has one. Combined with the in-process offline guard, *two independent mechanisms* block egress.
- **The reference machine** is a common laptop class (8 vCPU / 16 GB). The software must run the hero world end to end on it (targets in §14.3).

### 3.5.2 Cloud showroom (the demo)

```
   judge's browser
        │
        ├──► https://<site>.vercel.app          Astro: landing · docs · write-up · metrics · status
        │
        └──► https://<app>.vercel.app           SPA (same build, VITE_APP_MODE=demo)
                    │  fetch + SSE, Authorization: Bearer
                    ▼
             https://<api>.onrender.com         Render "Standard" (1 CPU / 2 GB, never sleeps)
             sutradhar-api-demo:<sha>           pulled from GHCR, deployed by deploy hook
             ├── APP_MODE=demo, SQLite (ephemeral, seeded at boot)
             ├── EMBEDDED_WORKER=true (1 subprocess)
             ├── /data baked into image: hero world + 3 extra scenarios, pre-analysed
             └── nightly reset 03:00 IST · uploads ≤ 25 MB, deleted after 60 min

   GitHub Actions ── build → GHCR ── deploy hook (imgURL=…:<sha>) ──► Render
   GitHub → Vercel Git integration ──────────────────────────────────► web + site
```

Full detail, config files and hardening are in Part 12.

## 3.6 The architectural invariants

`[DECISION]` These are written here, copied into `docs/INVARIANTS.md`, loaded into every AI coding session, and each one is asserted by a named test. This list stops the build drifting.

| # | Invariant | Enforced by |
|---|---|---|
| **I1** | The API and worker make **no outbound network connection** in `demo` or `airgap` mode. | `offline_guard` (wraps `socket.connect`, `getaddrinfo`) · internal-only Docker network · `test_offline_pipeline_no_network` (`docker run --network none`) |
| **I2** | Every derived edge carries `method`, `confidence`, `evidence_refs`, `model_version` and `run_id`. | `NOT NULL` in run-store DDL · `test_every_edge_has_evidence_envelope` |
| **I3** | A completed run is immutable. Its outputs are addressed by `result_digest`. | `run.duckdb` chmod 0444 after E19 · API opens read-only · `test_completed_run_is_read_only` |
| **I4** | Same dataset digest + same config + same model versions ⇒ **same result digest**. | Seeded randomness, fixed threads, explicit `ORDER BY` before every write · `test_run_is_deterministic` (runs twice) |
| **I5** | The audit log is append-only and hash-chained. | Postgres trigger `audit_log_append_only` + `REVOKE UPDATE, DELETE` · SQLite `RAISE(ABORT)` triggers · `test_audit_chain_verifies`, `test_audit_tamper_detected` |
| **I6** | Every published lead has a calibrated p, a grade, ≥ 1 reason and ≥ 1 supporting family. | `CHECK` constraints on `leads` · `test_every_lead_has_reason_grade_calibrated_p` |
| **I7** | Ground truth never reaches inference. | `import-linter` (engine ⟂ gen/evals) · truth files never mounted into `api`/`worker` in demo or airgap · `test_engine_cannot_import_truth` |
| **I8** | A transaction with `p_coinjoin ≥ τ_cj` never contributes a common-input merge. | E05 filter · `test_cioh_excludes_coinjoin` |
| **I9** | Money is `int64` **satoshis** everywhere inside. Never floats. | Schemas typed `Sats = int` · conversion via `Decimal` at I03 · `test_no_float_money` |
| **I10** | Time is stored as UTC microseconds (`int64`). Display converts with an explicit offset label. | Schema types · `test_timestamps_utc_micros` |
| **I11** | The web bundle contains no external URL and loads no external resource. | Build step `check-no-external-urls` · Playwright request audit `test_web_makes_no_external_requests` |
| **I12** | No list endpoint returns an unbounded list. | Cursor pagination dependency · `test_no_unpaginated_list_endpoints` |
| **I13** | Every state-changing API call writes an audit entry **in the same transaction**. | `@audited` service decorator · `test_every_mutation_emits_audit` |
| **I14** | A model version serves only after its evaluation report passes the promotion thresholds. | `models.promote()` gate · `test_promotion_blocked_below_threshold` |
| **I15** | XML is parsed with external entities, DTD loading and network access disabled. | `defusedxml` / hardened `lxml` parser · `test_xxe_payload_rejected`, `test_billion_laughs_rejected` |
| **I16** | Every CSV or spreadsheet export neutralises formula injection. | `safe_cell()` in exporters · `test_csv_injection_neutralised` |
| **I17** | Lead text is **hedged** (never asserts identity or guilt), and a grade is never shown without its evidence families. | Reason-template lint · UI component contract · `test_reason_templates_are_hedged` |
| **I18** | Module boundaries hold (§3.3). | `import-linter` in CI · `test_import_contract` |
| **I19** | Demo uploads are deleted after their TTL and never enter the demo snapshot. | Purge job · `test_demo_upload_ttl_purge` |
| **I20** | Every reference dataset (GeoIP, Tor, VPN, hosting) carries source, licence and as-of date, shown in the UI and recorded in manifests. | `refdata/manifest.json` · `test_enrichment_provenance_present` |

## 3.7 Technology decisions, with the reason each was chosen

Versions are **majors**. Exact versions are pinned in `uv.lock` and `pnpm-lock.yaml`, and upgraded deliberately.

| Layer | Choice | Version | Why this, and what it beat |
|---|---|---|---|
| Language (engine, API) | Python | 3.12 | The whole data/ML/graph ecosystem, one language across engine, API and generator. 3.12 over 3.13 for guaranteed wheels across LightGBM, igraph, DuckDB and WeasyPrint on amd64 and arm64. |
| Package / workspace | **uv** workspace | current | Fast, lockfile with hashes, workspaces for our six Python packages. Beat Poetry (slower, weaker workspaces) and pip-tools (no workspaces). |
| API framework | **FastAPI** + Pydantic v2 | current / 2.x | Typed models → OpenAPI → generated TS client. Async SSE. Thin. Beat Django (§3.2) and Flask (no typing or OpenAPI story). |
| App DB | **PostgreSQL** (airgap) / **SQLite** (demo) | 17 / 3.x | Postgres: constraints, triggers, `SKIP LOCKED` for the job queue. SQLite for the demo: nothing to expire, reset by restart. SQLAlchemy 2.0 spans both. |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | 2.x / 1.x | Boring, documented, works on both databases. |
| Analytics store | **DuckDB** file per dataset and per run | 1.x | Columnar, embedded, zero-server. A read-only file can be shared by many processes, which makes the run file itself the evidence artefact. Beat Parquet-only (no indexes or joins at query time) and ClickHouse (a server). |
| DataFrames | **Polars** | 1.x | Fast CSV/NDJSON parsing, lazy streaming, Arrow-native interchange with DuckDB. pandas only where a library demands it. |
| Graph algorithms | **python-igraph** + SciPy sparse | 0.11+ / 1.x | C-backed components, personalized PageRank, shortest paths. NetworkX only for small subgraphs and GraphML export. |
| ML | **LightGBM** + scikit-learn | 4.x / 1.x | Trees beat GNNs on this class of data (Weber et al. 2019; Elliptic++ 2023). CPU-only, deterministic mode, and **exact TreeSHAP via `pred_contrib=True`**, so the `shap` library and its numba stack stay out of the runtime image. |
| Embeddings | scikit-learn `randomized_svd` | 1.x | Deterministic, light, fast. node2vec (gensim/torch) is a `[STRETCH]` comparison, not a dependency. |
| GeoIP | **DB-IP Lite** `.mmdb` + `maxminddb` reader | monthly | CC BY 4.0, no account, direct download. GeoLite2 needs an account and its EULA requires deleting data within 30 days of a new release, which is awkward offline. IPinfo Lite (CC BY-SA 4.0) is optional. |
| XML | `defusedxml` + `lxml` iterparse | current | Streaming plus safe by construction (I15). |
| PDF | WeasyPrint | current | Server-side HTML→PDF, byte-stable, offline. |
| Auth | PyJWT + argon2-cffi | current | Bearer tokens work across the cross-site demo domains. argon2id for passwords. |
| CLI | Typer | current | One `sutradhar` command for every workflow. The same code runs in CI, in the worker and on a laptop. |
| Frontend | **React + Vite + TypeScript** | 19 / current / 5.x | Largest ecosystem; the static build runs on Vercel *and* offline behind Caddy. Next.js SSR would need a Node server in the air-gapped bundle. |
| Routing / data | TanStack Router + Query (+ Table, Virtual) | v1 / v5 | Type-safe URL search params (an analyst console lives in filtered URLs). Query-key invalidation. Virtualised 100k-row tables. |
| UI kit | Tailwind CSS + shadcn/ui (Radix) | v4 / current | Components copied into the repo (we own them); accessible primitives. |
| Link analysis | **Cytoscape.js** (+ fcose) and **Sigma.js** (+ graphology) | 3.x / 3.x | Cytoscape for rich interactive investigation (≤ ~2k nodes); Sigma's WebGL for overview graphs (≤ ~50k nodes). |
| Maps | **deck.gl** + Natural Earth GeoJSON | 9.x | Arc layers for flows with **no tile server**. Natural Earth is public domain. |
| Charts | Apache ECharts | current | Sankey, histograms, calibration curves. Canvas-rendered and fast. |
| Command palette | cmdk | current | ⌘K omnibox. |
| i18n | i18next | current | English and हिंदी UI labels. |
| Fonts | IBM Plex Sans / Mono via Fontsource | current | SIL OFL. **Self-hosted**: Google Fonts would break offline (I11). |
| Docs / landing | Astro + Starlight | current | Static, fast, Markdown-first. The write-up, model cards and metrics page all live here. |
| Edge (airgap) | Caddy | 2.x | Tiny config, static files and reverse proxy. `auto_https off` and `admin off` for offline. |
| Containers | Docker Engine + Compose v2 | current | The only runtime prerequisite on the target machine. |
| CI/CD | GitHub Actions + GHCR | – | Images built once in CI and deployed by digest (demo) or saved into the bundle (airgap). |
| Frontend hosting | **Vercel** (Hobby) | – | Static SPA and site, previews per PR. Backend is deliberately **not** on Vercel (§3.2). |
| Backend demo hosting | **Render** Standard, image-backed | – | Never sleeps (free tier sleeps after 15 min and takes about a minute to wake). 2 GB RAM. Deploys a GHCR image by digest via deploy hook. Railway Hobby is the documented alternative (§12.6). |

## 3.8 Trust boundaries and what crosses them

```
  ZONE                    WHAT LIVES THERE                        WHAT MAY CROSS INTO IT
  ──────────────────────────────────────────────────────────────────────────────────────────────
  Analyst browser         SPA, bearer token (memory/sessionStorage) —
        │
        │  HTTP on 127.0.0.1 (airgap) · HTTPS (demo) · CSP · rate limits
        ▼
  Edge (Caddy)            static assets, reverse proxy            only :8080 (airgap) / :443 (Vercel/Render)
        │
        │  internal Docker network, no default route
        ▼
  Application             API, worker, offline guard              only Caddy · only the app network
        │
        │  no published ports · credentials from .env / Docker secrets
        ▼
  Data                    Postgres, /data, /models (ro),          only the application zone
                          /refdata (ro)
  ──────────────────────────────────────────────────────────────────────────────────────────────
  Ground truth            generator truth files                   ONLY sutradhar_evals, ONLY in Lab jobs,
                                                                   NEVER mounted in demo/airgap inference
  ──────────────────────────────────────────────────────────────────────────────────────────────
  Internet                —                                        NOTHING, in either direction, in airgap.
                                                                   Demo: inbound HTTPS only; no outbound.
```

**Said plainly to a judge:**
1. Nothing in the product can call out. Two independent mechanisms stop it, and CI proves it on every change.
2. The model never sees the answers. The package that can read ground truth is walled off from the package that makes predictions, and a test enforces the wall.
3. Every change anyone makes is written into a chain of hashes. Editing history breaks the chain, and the auditor role can check it with one click.

---


# PART 4 — THE DATA ARCHITECTURE

> The data model decides what the system can and cannot ever do. Getting it right before the first endpoint is written is the cheapest week of the project. This part is that week.

## 4.1 Conventions

| Convention | Choice | Why |
|---|---|---|
| App-entity IDs | Typed ULIDs: `ds_01JB…`, `run_…`, `job_…`, `case_…`, `exp_…`, `usr_…`, `mdl_…` | Time-sortable, mintable anywhere (including in the generator and CLI), and readable in logs. The prefix tells you the type at a glance. |
| Natural keys | `txid` = lowercase 64-hex · `address` = trimmed, case preserved (bech32 lowercased) · `ip` = canonical form from Python `ipaddress` (IPv6 compressed) · `asn` = integer | One canonical spelling per real thing, so joins never miss. |
| Run-store integer keys | Dictionary-encoded `tx_i`, `addr_i`, `ip_i`, `ent_i`, `actor_i` (`INTEGER`), with `d_*` tables mapping back to natural keys | Graph algorithms (SciPy, igraph) want dense integer IDs. Natural keys stay one join away. |
| Time | `int64` **UTC microseconds** (`ts_us`) | Sub-millisecond relay timing matters for origin attribution. Integers sort and diff exactly. |
| Display time | IST (`Asia/Kolkata`) by default, **always shown with its offset label**, and switchable to UTC | Analysts in India think in IST. Evidence must never be ambiguous about timezone. |
| Money | `int64` **satoshis** (`Sats`). BTC only at display, 8 decimal places | Floats corrupt money. Satoshis are exact (I9). |
| Hashes | SHA-256, lowercase hex | Matches the BSA 2023 s.63 certificate options and every verification tool. |
| Canonical JSON (for hashing) | UTF-8, keys sorted, no insignificant whitespace, floats rounded to 6 decimals before serialising | The same object always hashes the same. |
| Enumerations | `text` + `CHECK (col IN (…))`, mirrored by Python `StrEnum` | Adding a value is a one-line migration. Native enums are painful to change. |
| JSON columns | `jsonb` (Postgres) / `JSON` (SQLite) via SQLAlchemy `JSON` | One model definition for both databases. |
| Deletion | Evidence is **never deleted**. Cases are archived. Demo uploads expire by TTL. | An evidence system that forgets is not one. |

## 4.2 The canonical input record — data contract v1

One canonical record describes **one observed network event that carried a transaction**. A transaction relayed to 30 sensors appears in up to 30 records. That repetition is the signal the correlation engine lives on.

| Field | Type | Req. | Notes | PS field |
|---|---|:-:|---|---|
| `timestamp` | ISO-8601 string · or epoch s / ms / µs number | ✓ | Epoch unit auto-detected by magnitude. ISO without an offset is read as **UTC** `[DEFAULT]` (profile override). | timestamp |
| `src_ip` | string | ✓¹ | IPv4 or IPv6 | src_ip |
| `dst_ip` | string | ✓¹ | IPv4 or IPv6 | dst_ip |
| `src_port` | int | ✓¹ | 0–65535 | src_port |
| `dst_port` | int | ✓¹ | 0–65535 (8333 = Bitcoin mainnet default) | dst_port |
| `txid` | string | ✓ | 64 hex chars, lowercased on ingest | txid |
| `input_addresses` | string[] | ✓ | Empty only for coinbase | input_addresses[] |
| `output_addresses` | string[] | ✓ | Non-empty | output_addresses[] |
| `input_amounts` | number[] | ✓ | Aligned 1:1 with `input_addresses` | input_amounts[] |
| `output_amounts` | number[] | ✓ | Aligned 1:1 with `output_addresses` | output_amounts[] |
| `fee` | number | – | **Computed** as Σin − Σout when absent, and cross-checked when present | fee |
| `script_type` | string · or per-io arrays `input_script_types[]` / `output_script_types[]` | – | **Inferred from the address format** when absent (§4.3.3) | script type |
| `geo_country` | ISO-3166 alpha-2 | – | Kept as `geo_country_src`. **Our enrichment** fills `country` with provenance, and disagreements are flagged. | geo_country |
| `asn` | int or `"AS1234"` | – | Kept as `asn_src`. Enrichment fills `asn`. | asn |
| *optional* `input_prevouts` | string[] `"txid:vout"` | – | When present, exact UTXO links replace (address, amount) matching | – |
| *optional* `block_height`, `block_time` | int | – | Used for confirmation-delay features | – |
| *optional* `vsize`, `locktime`, `version`, `rbf` | int / bool | – | Fee-rate and wallet-fingerprint features when present | – |
| *optional* `sensor_id`, `direction`, `msg_type` | string | – | Explicit vantage labelling (`inv`/`tx`) when the capture tool provides it | – |

¹ Network fields are required **for correlation**. Without them the dataset still ingests in **chain-only mode**: every blockchain feature works, NET-family features are switched off, and the X-ray says so (R-PS-15, `test_chain_only_mode`).

**Amount units.** Amounts arrive as BTC (decimal) or satoshis (integer). The profile may say `amount_unit: btc | sat | auto`.
- In `auto`, a dataset is read as **satoshis** if every amount is an integer **and** the median non-zero amount is ≥ 1,000. Otherwise it is read as BTC.
- The X-ray shows the decision and the evidence (median, integer share), so a wrong guess is visible and one click to fix.

## 4.3 Physical encodings accepted

### 4.3.1 Formats

| Format | Detection | Array encoding accepted | Reader |
|---|---|---|---|
| CSV / TSV | extension + sniffing | JSON-in-cell `["a","b"]` · delimiter-joined `a;b` / `a\|b` · indexed columns `input_address_0…n` | Polars streaming CSV |
| JSON (array of objects) | leading `[` | native arrays | `ijson` streaming (never `json.load` on a 2 GB file) |
| NDJSON / JSON Lines | one object per line | native arrays | Polars NDJSON streaming |
| XML | leading `<` | repeated child elements (`<input><address/><amount/></input>`) · wrapper lists (`<input_addresses><address/>…`) | `defusedxml` + `lxml.iterparse` with `resolve_entities=False`, `no_network=True`, `huge_tree=False` |
| gzip / zstd of any of the above | magic bytes | – | streaming decompress, with a decompression-ratio guard of 200:1 `[DEFAULT]` |

Full example records in all three formats are in §17.5.

### 4.3.2 Mapping profiles

A mapping profile is a small YAML document. It turns any source layout into the canonical record without code changes. The auto-mapper proposes one, the analyst confirms or edits it in the wizard, and it is saved and versioned. Every normalised dataset records the profile **and its hash** in its manifest.

```yaml
# profiles/ntro-flowlog-v1.yaml  (illustrative)
profile: ntro-flowlog-v1
version: 3
format: csv                # csv | tsv | json | ndjson | xml
csv: { delimiter: ",", quote: '"', header: true, encoding: utf-8 }
xml: { record_xpath: "/capture/event" }          # only for xml
timestamp: { field: "ts", unit: auto, tz: "UTC" } # iso | s | ms | us | auto
amount_unit: auto                                  # btc | sat | auto
fields:
  src_ip:           { field: "source.ip" }
  src_port:         { field: "source.port", cast: int }
  dst_ip:           { field: "dest.ip" }
  dst_port:         { field: "dest.port", cast: int }
  txid:             { field: "tx_hash", transform: lower }
  input_addresses:  { field: "vin_addrs", array: { encoding: json } }
  input_amounts:    { field: "vin_vals",  array: { encoding: delimited, sep: ";" } }
  output_addresses: { field: "vout_addrs", array: { encoding: json } }
  output_amounts:   { field: "vout_vals",  array: { encoding: delimited, sep: ";" } }
  fee:              { field: "fee", optional: true }
  script_type:      { field: "stype", optional: true }
  geo_country:      { field: "cc", optional: true }
  asn:              { field: "asn", optional: true, transform: strip_as_prefix }
```

**The auto-mapper** scores each source column against each canonical field. It uses name similarity (normalised tokens plus a synonym table: `tx_hash`, `hash`, `transaction_id` → `txid`) and *value-shape* checks on a 1,000-row sample (64-hex → txid; dotted quads → IP; 0–65535 integers with many 8333s → port; arrays of base58/bech32 strings → addresses). It proposes the best assignment with a confidence per field. Low-confidence fields are highlighted in the wizard.

### 4.3.3 Script-type inference from the address

| Prefix / shape (mainnet) | Inferred type | Testnet/signet equivalent |
|---|---|---|
| `1…` (base58, 25–34 chars) | `p2pkh` | `m…` / `n…` |
| `3…` (base58) | `p2sh` (incl. wrapped segwit) | `2…` |
| `bc1q…` length 42 | `p2wpkh` | `tb1q…` length 42 |
| `bc1q…` length 62 | `p2wsh` | `tb1q…` length 62 |
| `bc1p…` | `p2tr` | `tb1p…` |
| anything else | `unknown` (warn V12) | – |

Synthetic datasets may use random address strings. Inference then yields `unknown` and script-type features are switched off by capability detection. They are never guessed.

## 4.4 Validation rules

Every rule has an ID, a severity and an action. Rejected rows are written to `rejects` with the rule ID and the offending value, and are downloadable as CSV (neutralised per I16).

| ID | Rule | Severity | Action |
|---|---|---|---|
| V01 | `txid` is 64 hex characters | error | reject row |
| V02 | `src_ip`/`dst_ip` parse as IPv4/IPv6 (when network mode) | error | reject row |
| V03 | Ports are integers in 0–65535 | error | reject row |
| V04 | `timestamp` parses and lies in [2009-01-03, ingest time + 1 day] | error | reject row |
| V05 | `len(input_addresses) == len(input_amounts)` and the same for outputs | error | reject row |
| V06 | Amounts ≥ 0 and ≤ 21,000,000 BTC | error | reject row |
| V07 | `output_addresses` non-empty | error | reject row |
| V08 | Σout ≤ Σin (unless coinbase: no inputs) | error | quarantine txid |
| V09 | `fee` present and \|fee − (Σin − Σout)\| > 1 sat | warning | keep, use computed fee, flag |
| V10 | Same txid seen with **different** inputs/outputs in another row | error | quarantine txid (all rows), report both variants |
| V11 | Exact duplicate row (txid, src, dst, ports, timestamp) | info | drop duplicate, count |
| V12 | Address fails format plausibility (length 14–90, allowed charset) | warning | keep, `script_type = unknown` |
| V13 | Private/bogon/reserved IP (RFC 1918, 100.64/10, 127/8, ::1, fc00::/7…) | warning | keep, `is_bogon = true` (the source may be NAT-internal) |
| V14 | `src_ip == dst_ip` | warning | keep, flag |
| V15 | Provided `geo_country`/`asn` disagrees with enrichment | info | keep both, flag disagreement |
| V16 | Timestamp non-monotonic per (txid, sensor) beyond clock tolerance | info | keep, used by skew estimation |
| V17 | Zero-value outputs (OP_RETURN-like) | info | keep, excluded from value features |
| V18 | Row missing network fields while others have them | warning | keep in chain layer, excluded from correlation |
| V19 | More than 5,000 inputs or outputs in one tx | warning | keep, capped in feature computation |
| V20 | Row size > 1 MB or nesting depth > 32 | error | reject row (parser guard) |

A dataset whose reject rate exceeds 20% `[DEFAULT]` is held in `VALIDATED` with a banner and not auto-run. It usually means a wrong mapping profile, and running anyway would waste minutes producing nonsense.

## 4.5 Capability detection and the Dataset X-ray

I06 computes a **capability profile**, and E01 uses it to switch features on or off. The X-ray screen renders it within a minute of upload.

```json
{
  "rows": 1528214, "txs": 61377, "addresses": 212904, "ips": 3981,
  "span": {"from": "2026-08-01T00:00:03Z", "to": "2026-08-22T23:59:41Z"},
  "amount_unit": {"decision": "sat", "integer_share": 1.0, "median_nonzero": 184000},
  "network": {
    "present": true,
    "observation_model": "mixed",          // vantage | flow | mixed | single | none
    "distinct_dst_ips": 57, "dst_8333_share": 0.93,
    "obs_per_tx": {"p50": 24, "p90": 41},
    "sensors_inferred": 40
  },
  "fields": {"fee": "computed", "script_type": "inferred", "prevouts": false, "geo_src": true},
  "quality": {"reject_rate": 0.0031, "duplicate_rate": 0.012, "conflict_txids": 3},
  "enabled_stages": ["E01","E02","E03","E04","E05","E06","E07","E08","E09","E10","E11","E12","E13","E14","E15","E16","E17","E18","E19"],
  "disabled_features": [],
  "warnings": ["3 txids quarantined for conflicting content (V10)"]
}
```

**Observation-model detection** decides how the correlation engine reasons:

| Model | Signature in the data | What it means | What E10 relies on |
|---|---|---|---|
| **vantage** | Few distinct `dst_ip`s (≤ 5% of IPs), mostly on port 8333, each seeing many txids | A handful of listening sensors record what their peers announce | First-arrival ranks across sensors, relayer base rates, re-broadcasts |
| **flow** | Many distinct `dst_ip`s; records between arbitrary peers | ISP-level flow logs between nodes | **Sent-before-received**: a node that sends a txid before ever receiving it is a strong origin candidate |
| **mixed** | Both signatures present | Sensors plus partial flow visibility | Both feature families |
| **single** | Exactly one record per txid | The file already states an origin per transaction | Attribution is *taken from the record*, and the UI labels it "as reported", not inferred |
| **none** | No network fields | Chain-only | NET family disabled |

## 4.6 The dataset store — `datasets/<id>/dataset.duckdb`

Written once by I03–I06, then read-only for every run over it.

```sql
-- one row per observed relay event
CREATE TABLE obs (
  obs_i        BIGINT PRIMARY KEY,         -- row order after dedupe, stable
  ts_us        BIGINT  NOT NULL,           -- UTC microseconds
  src_ip       VARCHAR,                    -- canonical text; NULL in chain-only rows
  src_port     INTEGER,
  dst_ip       VARCHAR,
  dst_port     INTEGER,
  txid         VARCHAR NOT NULL,
  file_id      VARCHAR NOT NULL,           -- dataset_files.id
  row_no       BIGINT  NOT NULL,           -- line/record number in that file (evidence pointer)
  geo_src      VARCHAR, asn_src INTEGER    -- as provided, never trusted blindly
);
-- one row per distinct transaction (content taken from first valid observation)
CREATE TABLE tx (
  txid VARCHAR PRIMARY KEY, first_seen_us BIGINT NOT NULL, last_seen_us BIGINT NOT NULL,
  n_in INTEGER NOT NULL, n_out INTEGER NOT NULL,
  in_sats BIGINT NOT NULL, out_sats BIGINT NOT NULL, fee_sats BIGINT NOT NULL,
  fee_src VARCHAR NOT NULL CHECK (fee_src IN ('provided','computed')),
  is_coinbase BOOLEAN NOT NULL, block_height INTEGER, vsize INTEGER, locktime BIGINT, version INTEGER, rbf BOOLEAN
);
CREATE TABLE txin  (txid VARCHAR, idx INTEGER, address VARCHAR, sats BIGINT, script_type VARCHAR, prevout VARCHAR,
                    PRIMARY KEY (txid, idx));
CREATE TABLE txout (txid VARCHAR, idx INTEGER, address VARCHAR, sats BIGINT, script_type VARCHAR,
                    PRIMARY KEY (txid, idx));
CREATE TABLE rejects    (file_id VARCHAR, row_no BIGINT, rule VARCHAR, field VARCHAR, value VARCHAR, message VARCHAR);
CREATE TABLE quarantine (txid VARCHAR, rule VARCHAR, variants JSON);
CREATE TABLE dataset_meta (key VARCHAR PRIMARY KEY, value JSON);   -- profile, profile_hash, xray, digests
```

## 4.7 The graph model

### 4.7.1 Node types

| Node | Key | Where from | Notes |
|---|---|---|---|
| `IP` | canonical IP | `obs.src_ip/dst_ip` | Enriched: country, ASN, AS org, Tor exit, VPN, hosting, bogon, role (listener/client) |
| `SESSION` | (ip, src_port, window) | E09 | One TCP connection's lifetime. Stronger identity than an IP behind NAT. |
| `SENSOR` | canonical IP | E02 inference or explicit `sensor_id` | Carries estimated clock skew |
| `TX` | txid | `tx` | Carries CoinJoin probability, anomaly score, taint |
| `ADDRESS` | address | `txin`/`txout` | Carries script type, first/last seen |
| `ENTITY` | `ent_i` | E05 (+E06) | Common-input cluster (with high-confidence change merges) |
| `ACTOR` | `actor_i` | E13 | One or more entities judged to be the same operator |
| `ASN`, `COUNTRY` | number / ISO code | E02 | Aggregation nodes for the geo views |

### 4.7.2 Edge types (sixteen)

| # | Edge | From → To | Method(s) | Confidence meaning |
|---|---|---|---|---|
| 1 | `RELAYED` | IP/SESSION → TX | `obs` | 1.0 (observed) |
| 2 | `CONNECTED` | IP → SENSOR | `obs` | 1.0 (observed) |
| 3 | `SPENDS` | ADDRESS → TX | `obs` | 1.0 |
| 4 | `PAYS` | TX → ADDRESS | `obs` | 1.0 |
| 5 | `FLOWS_TO` | TX → TX | `prevout` · `addr_amount_match` | 1.0 for prevout; match certainty otherwise |
| 6 | `MEMBER_OF` | ADDRESS → ENTITY | `cioh` · `change_model` · `analyst_assertion` | 1.0 CIOH (as a *heuristic*, flagged); p for change |
| 7 | `CHANGE_OF` | ADDRESS → TX | `change_model` | p(change) |
| 8 | `PEEL_NEXT` | TX → TX | `peel_model` | chain p |
| 9 | `ORIGINATED` | IP/SESSION → TX | `origin_model` · `as_reported` | calibrated p(origin) |
| 10 | `CONTROLS` | IP/SESSION → ENTITY | `control_agg` | noisy-OR over attributed txs |
| 11 | `CO_ORIGIN` | ENTITY — ENTITY | `co_origin` | IDF-weighted shared-origin strength |
| 12 | `SAME_ACTOR` | ENTITY → ACTOR | `er_model` · `analyst_assertion` | p(same owner) |
| 13 | `SIMILAR` | ENTITY — ENTITY | `embed_sim` | cosine (used for suggestions only) |
| 14 | `IN_ASN` | IP → ASN | `geoip:<source>@<as_of>` | 1.0 (database fact, dated) |
| 15 | `IN_COUNTRY` | IP/ASN → COUNTRY | `geoip:<source>@<as_of>` | 1.0 (database fact, dated) |
| 16 | `TAINT_PATH` | ENTITY/ACTOR → ENTITY/ACTOR | `haircut` · `ppr` | taint fraction carried along the path |

### 4.7.3 The evidence envelope

Every **derived** edge row (types 5–16) carries the same five columns (I2):

```sql
method         VARCHAR NOT NULL,   -- one of the methods above
confidence     DOUBLE  NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
evidence_refs  JSON    NOT NULL,   -- e.g. {"txids":[…], "obs":[[file_id,row_no],…], "rules":["V08"]}
model_version  VARCHAR NOT NULL,   -- "origin_ranker@1.3.0" | "rules@1" | "geoip:dbip-lite@2026-09"
run_id         VARCHAR NOT NULL
```

`evidence_refs.obs` points back to **exact source rows** (`file_id`, `row_no`). Any claim can therefore be traced to the lines of the original file, which is what an evidence pack cites.

## 4.8 The run store — `runs/<id>/run.duckdb`

Written by E01–E19 and made read-only at E19. The catalogue below lists the key columns. The complete DDL lives in `packages/engine/sutradhar_engine/store/ddl.sql` and is the source of truth.

| Table | Key columns | Stage |
|---|---|---|
| `d_tx`, `d_addr`, `d_ip` | `tx_i`↔`txid` · `addr_i`↔`address`,`script_type` · `ip_i`↔`ip` | E01 |
| `ip_enrich` | `ip_i`, `country`, `asn`, `as_org`, `is_tor_exit`, `is_vpn`, `is_hosting`, `is_bogon`, `role` (`listener`/`client`/`sensor`/`unknown`), `refdata_version` | E02 |
| `sensor` | `ip_i`, `kind` (`vantage`/`flow_tap`), `skew_us`, `skew_ci_us` | E02/E09 |
| `flow` | `src_tx_i`, `dst_tx_i`, `addr_i`, `sats`, **envelope** | E03 |
| `utxo_spend` | `tx_i`, `out_idx`, `spent_by_tx_i`, `dt_us` | E03 |
| `cj` | `tx_i`, `p_coinjoin`, `kind_pred` (`whirlpool_like`/`wasabi_like`/`joinmarket_like`/`generic`/`batch`/`none`), `top_features` | E04 |
| `entity`, `entity_member` | `ent_i`, sizes, spans, `suspect_mega` · `addr_i`, `ent_i`, **envelope** | E05/E06 |
| `change_link` | `tx_i`, `out_idx`, `addr_i`, `p_change`, `merged` | E06 |
| `peel_chain`, `peel_hop` | `chain_i`, `p`, `n_hops`, `total_peeled_sats` · `chain_i`, `hop`, `tx_i`, `peel_addr_i`, `peel_sats`, `dt_s` | E07 |
| `motif_hit` | `hit_i`, `detector@version`, `subject_kind`, `subject_i`, `score`, `members`, `window` | E08 |
| `session` | `sess_i`, `ip_i`, `src_port`, `first_us`, `last_us`, `n_obs` | E09 |
| `origin_cand` | `tx_i`, `ip_i`, `sess_i`, feature columns…, `p` | E10 |
| `origin` | `tx_i`, `ip_i` (nullable), `sess_i`, `p_top`, `p_unobservable`, `n_cand`, **envelope** | E10 |
| `control`, `co_origin` | `ip_i`/`sess_i`, `ent_i`, `p`, `n_tx`, `crowdedness` · `ent_a`, `ent_b`, `strength`, **envelope** | E11 |
| `embedding` | `ent_i`, `v FLOAT[32]` | E12 |
| `er_pair`, `actor`, `actor_member` | `ent_a`, `ent_b`, `p`, `decision` · `actor_i`, sizes · `ent_i`, `actor_i`, **envelope** | E13 |
| `service` | `actor_i`, `service_score`, `service_type` (`exchange`/`mixer`/`gambling`/`pool`/`merchant`/`unknown`) | E14 |
| `seed` | `addr_i` or `ip_i`, `category`, `source`, `confidence`, `watchlist_id` | E15 |
| `risk`, `risk_path` | `node_kind`, `node_i`, `taint_frac`, `taint_sats`, `ppr`, `hops_to_seed`, `exposure_out`, `victim_like` · `rank`, `path` (JSON), `strength` | E15 |
| `anomaly` | `node_kind`, `node_i`, `score`, `pct` | E16 |
| `feat_actor` | `actor_i`, ~70 named features (§7.3.7) | E17 |
| `lead` | `lead_i`, `lead_key`, `type`, `subject_kind`, `subject_i`, `p`, `grade`, `priority`, `families`, `value_at_risk_sats`, `last_activity_us`, `reasons` | E17/E18 |
| `lead_contrib`, `lead_cf`, `lead_subgraph` | per-feature TreeSHAP contributions · counterfactual steps · explanation subgraph (nodes/edges JSON) | E18 |
| `tz_profile` | `actor_i`, `offset_min`, `confidence`, `hist INTEGER[24]` | E18 |
| `drift` | `model`, `feature`, `psi`, `severity` | E17 |
| `run_meta` | `key`, `value` (manifest, timings, row counts, digests) | all |

`lead_key` is `sha256(type ‖ subject_kind ‖ canonical subject)[:16]`, where the canonical subject is the sorted member-address set for ACTORs, the address for CASHOUT, the ordered txid list for CHAIN, the txid for TX, and the IP for IP. It is stable across runs, and that stability is what carries triage state forward (§2.5.3).

## 4.9 The app database — DDL (PostgreSQL 17; SQLite-compatible via SQLAlchemy)

```sql
-- ─── identity ────────────────────────────────────────────────────────────────
CREATE TABLE users (
  id            text PRIMARY KEY,                       -- usr_…
  email         text NOT NULL UNIQUE,
  name          text NOT NULL,
  role          text NOT NULL CHECK (role IN ('analyst','lead','admin','auditor','demo')),
  password_hash text NOT NULL,                          -- argon2id
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz
);
CREATE TABLE sessions (                                 -- refresh tokens (hashed)
  id           text PRIMARY KEY,
  user_id      text NOT NULL REFERENCES users(id),
  refresh_hash text NOT NULL UNIQUE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz,
  client_ip    text, user_agent text
);

-- ─── data ────────────────────────────────────────────────────────────────────
CREATE TABLE mapping_profiles (
  id text PRIMARY KEY, name text NOT NULL, version int NOT NULL,
  spec jsonb NOT NULL, spec_sha256 text NOT NULL, is_builtin boolean NOT NULL DEFAULT false,
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (name, version)
);
CREATE TABLE datasets (
  id text PRIMARY KEY,                                  -- ds_…
  name text NOT NULL,
  status text NOT NULL CHECK (status IN ('uploaded','mapped','validated','normalised','failed')),
  source text NOT NULL CHECK (source IN ('upload','watch','generator','cli')),
  series_id text,                                       -- monitoring series
  profile_id text REFERENCES mapping_profiles(id),
  raw_digest text, normalised_digest text,
  xray jsonb, row_count bigint, reject_count bigint, bytes bigint,
  expires_at timestamptz,                               -- demo uploads only (I19)
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE dataset_files (
  id text PRIMARY KEY, dataset_id text NOT NULL REFERENCES datasets(id),
  filename text NOT NULL, format text NOT NULL, sha256 text NOT NULL, bytes bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE runs (
  id text PRIMARY KEY,                                  -- run_…
  dataset_id text NOT NULL REFERENCES datasets(id),
  prev_run_id text REFERENCES runs(id),
  status text NOT NULL CHECK (status IN ('queued','running','completed','failed','published')),
  stage text,                                           -- E01…E19 while running
  config jsonb NOT NULL, model_versions jsonb NOT NULL, refdata_versions jsonb NOT NULL,
  manifest jsonb, result_digest text,
  error text, started_at timestamptz, finished_at timestamptz,
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);

-- ─── jobs (the queue) ────────────────────────────────────────────────────────
CREATE TABLE jobs (
  id text PRIMARY KEY,                                  -- job_…
  kind text NOT NULL CHECK (kind IN ('ingest','run','generate','evaluate','redteam','planner',
                                     'export','verify','retrain','purge','demo_reset')),
  payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
  priority int NOT NULL DEFAULT 100,
  attempts int NOT NULL DEFAULT 0, max_attempts int NOT NULL DEFAULT 1,
  idempotency_key text UNIQUE,
  locked_by text, locked_at timestamptz, heartbeat_at timestamptz,
  result jsonb, error text,
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz, finished_at timestamptz
);
CREATE INDEX jobs_ready ON jobs (priority, created_at) WHERE status = 'queued';
CREATE TABLE job_events (                               -- progress stream for SSE
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id text NOT NULL REFERENCES jobs(id),
  ts timestamptz NOT NULL DEFAULT now(), kind text NOT NULL, data jsonb NOT NULL
);

-- ─── leads & triage ──────────────────────────────────────────────────────────
CREATE TABLE leads (                                    -- published summary; content immutable
  id text PRIMARY KEY, run_id text NOT NULL REFERENCES runs(id),
  lead_key text NOT NULL,
  type text NOT NULL CHECK (type IN ('ACTOR','CASHOUT','CHAIN','TX','IP')),
  subject_kind text NOT NULL, subject_ref text NOT NULL,
  p double precision NOT NULL CHECK (p >= 0 AND p <= 1),
  grade text NOT NULL CHECK (grade IN ('A','B','C')),
  priority double precision NOT NULL,
  families jsonb NOT NULL CHECK (jsonb_array_length(families) >= 1),   -- I6
  reasons  jsonb NOT NULL CHECK (jsonb_array_length(reasons)  >= 1),   -- I6
  value_at_risk_sats bigint NOT NULL DEFAULT 0,
  last_activity_at timestamptz,
  title text NOT NULL, summary text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, lead_key)
);
CREATE INDEX leads_queue ON leads (run_id, priority DESC);
CREATE TABLE lead_state (                               -- workflow; survives re-runs
  lead_key text PRIMARY KEY,
  status text NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','IN_REVIEW','ESCALATED','CONFIRMED','DISMISSED','SNOOZED')),
  assignee_id text REFERENCES users(id), snooze_until timestamptz,
  last_seen_run_id text REFERENCES runs(id), changed_since_review boolean NOT NULL DEFAULT false,
  updated_by text REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE feedback (
  id text PRIMARY KEY, lead_key text NOT NULL, run_id text NOT NULL REFERENCES runs(id),
  user_id text NOT NULL REFERENCES users(id),
  verdict text NOT NULL CHECK (verdict IN ('confirm','dismiss','escalate')),
  reason_code text CHECK (reason_code IN ('benign_service','victim','duplicate','insufficient_evidence',
                                          'known_false_positive_pattern','other')),
  note text, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (verdict <> 'dismiss' OR reason_code IS NOT NULL)            -- dismissals need a reason
);
CREATE TABLE merge_decisions (                          -- analyst assertions for E13
  id text PRIMARY KEY, a_ref text NOT NULL, b_ref text NOT NULL,      -- canonical entity refs
  decision text NOT NULL CHECK (decision IN ('accept','reject')),
  reason text NOT NULL, user_id text NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (a_ref, b_ref)
);
CREATE TABLE watchlists (
  id text PRIMARY KEY, name text NOT NULL, kind text NOT NULL CHECK (kind IN ('address','ip')),
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE watchlist_items (
  id text PRIMARY KEY, watchlist_id text NOT NULL REFERENCES watchlists(id),
  value text NOT NULL,
  category text NOT NULL CHECK (category IN ('ransomware','darknet','scam','theft','sanctioned','mixer','other')),
  source text NOT NULL, confidence double precision NOT NULL CHECK (confidence > 0 AND confidence <= 1),
  added_by text REFERENCES users(id), added_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (watchlist_id, value)
);

-- ─── cases & evidence ────────────────────────────────────────────────────────
CREATE TABLE cases (
  id text PRIMARY KEY, title text NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed','archived')),
  owner_id text NOT NULL REFERENCES users(id), summary text,
  created_at timestamptz NOT NULL DEFAULT now(), closed_at timestamptz
);
CREATE TABLE case_items (
  id text PRIMARY KEY, case_id text NOT NULL REFERENCES cases(id),
  item_kind text NOT NULL CHECK (item_kind IN ('lead','actor','entity','address','tx','ip','chain')),
  ref text NOT NULL, run_id text NOT NULL REFERENCES runs(id),
  note text, added_by text NOT NULL REFERENCES users(id), added_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE case_notes (
  id text PRIMARY KEY, case_id text NOT NULL REFERENCES cases(id),
  author_id text NOT NULL REFERENCES users(id), body_md text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE exports (
  id text PRIMARY KEY, case_id text REFERENCES cases(id),
  kind text NOT NULL CHECK (kind IN ('evidence_pack','misp','stix','graphml','i2csv','pdf')),
  status text NOT NULL CHECK (status IN ('queued','ready','failed')),
  file_path text, sha256 text, bytes bigint, manifest jsonb,
  created_by text NOT NULL REFERENCES users(id), approved_by text REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE verifications (
  id text PRIMARY KEY, file_sha256 text NOT NULL, result jsonb NOT NULL,
  verified_by text NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);

-- ─── models, lab, settings ───────────────────────────────────────────────────
CREATE TABLE models (
  id text PRIMARY KEY, name text NOT NULL, version text NOT NULL,
  status text NOT NULL CHECK (status IN ('candidate','shadow','active','retired')),
  artefact_sha256 text NOT NULL, metrics jsonb NOT NULL, trained_on jsonb NOT NULL, card_md text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), promoted_by text REFERENCES users(id), promoted_at timestamptz,
  UNIQUE (name, version)
);
CREATE UNIQUE INDEX one_active_model ON models (name) WHERE status = 'active';
CREATE TABLE scenarios (
  id text PRIMARY KEY, name text NOT NULL, spec jsonb NOT NULL, seed bigint NOT NULL,
  status text NOT NULL, dataset_id text REFERENCES datasets(id), truth_path text,
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE evaluations (
  id text PRIMARY KEY, kind text NOT NULL CHECK (kind IN ('eval','redteam','planner')),
  spec jsonb NOT NULL, status text NOT NULL, report jsonb,
  created_by text REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE academy_challenges (
  id text PRIMARY KEY, title text NOT NULL, scenario_id text NOT NULL REFERENCES scenarios(id),
  questions jsonb NOT NULL, time_limit_s int NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE academy_attempts (
  id text PRIMARY KEY, challenge_id text NOT NULL REFERENCES academy_challenges(id),
  user_id text NOT NULL REFERENCES users(id), answers jsonb NOT NULL,
  score double precision NOT NULL, duration_s int NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE refdata (
  source text NOT NULL, as_of date NOT NULL, license text NOT NULL, sha256 text NOT NULL,
  path text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (source, as_of)
);
CREATE TABLE settings (
  key text PRIMARY KEY, value jsonb NOT NULL,
  updated_by text REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now()
);

-- ─── audit (append-only, hash-chained) ── I5 ─────────────────────────────────
CREATE TABLE audit_log (
  seq         bigint PRIMARY KEY,                       -- gapless, assigned under audit_head lock
  ts          timestamptz NOT NULL,
  actor_id    text, actor_role text NOT NULL,           -- 'system' for jobs
  action      text NOT NULL,                            -- e.g. 'lead.dismiss', 'model.promote'
  target_kind text NOT NULL, target_ref text NOT NULL,
  payload     jsonb NOT NULL,
  prev_hash   text NOT NULL,
  entry_hash  text NOT NULL UNIQUE
);
CREATE TABLE audit_head (id smallint PRIMARY KEY CHECK (id = 1), seq bigint NOT NULL, entry_hash text NOT NULL);
INSERT INTO audit_head VALUES (1, 0, repeat('0', 64));   -- genesis

CREATE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END $$;
CREATE TRIGGER audit_no_update_delete BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only();
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM sutradhar_app;
```

**SQLite equivalents** (demo mode), generated from the same Alembic migration by dialect:
```sql
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
-- CHECK constraints use json_array_length(...) instead of jsonb_array_length(...)
```

## 4.10 Manifests and digests

**Dataset digest.** `raw_digest` = SHA-256 over the list of `(filename, sha256)` sorted by filename, plus the mapping profile's `spec_sha256`. `normalised_digest` = the table digest (below) of `obs`, `tx`, `txin` and `txout`.

**Table digest.** SHA-256 over rows serialised as canonical JSON Lines **in primary-key order**, streamed in Arrow batches. It is implemented once in `sutradhar_engine.digest` and used everywhere. It is slower than hashing Parquet bytes, but it is independent of file-format versions, which is what a verification three months later needs.

**Run manifest.** Written at E19 into `run_meta` and the app DB. It is the single document that makes a run reproducible:

```json
{
  "run_id": "run_01JBX8…",
  "dataset": {"id": "ds_01JBX4…", "raw_digest": "9f2c…", "normalised_digest": "41aa…",
              "profile": "ntro-flowlog-v1@3", "profile_sha256": "c01d…"},
  "code": {"version": "1.0.0", "git_sha": "4e1b9c2", "image_digest": "sha256:77e0…"},
  "models": {"coinjoin_clf": "1.2.0", "change_clf": "1.1.0", "peel_scorer": "1.0.3",
             "origin_ranker": "1.3.0", "er_pair_clf": "1.0.1", "anomaly_iforest": "1.0.0",
             "lead_ranker": "1.4.0"},
  "model_sha256": {"origin_ranker": "a4b2…", "…": "…"},
  "refdata": {"dbip-country-lite": "2026-09", "dbip-asn-lite": "2026-09",
              "tor-exits": "2026-09-28", "x4bnet-vpn": "2026-09-28", "x4bnet-dc": "2026-09-28"},
  "config": {"seed": 2026, "threads": 8, "settings_sha256": "e3b0…", "watchlists": ["wl_01…@7"]},
  "stages": {"E01": {"ms": 812, "rows": {"obs": 1528214}}, "…": {}},
  "result_digest": "5d0f…",
  "result_tables": ["entity_member","origin","control","actor_member","risk","lead","lead_contrib"]
}
```

**Result digest** = SHA-256 over the table digests of `result_tables`, in the listed order. `test_run_is_deterministic` runs the hero world twice and asserts equality (I4).

## 4.11 Sizes and retention

| Artefact | Hero world (≈1.5 M obs · 60 k tx) | Rule |
|---|---|---|
| Raw upload (CSV) | ~900 MB | Kept for the dataset's life (evidence) |
| `dataset.duckdb` | ~180–250 MB | Kept while any run references it |
| `run.duckdb` | ~250–400 MB | Last **5** runs per dataset `[DEFAULT]`. A run referenced by any case or export is **never** pruned. |
| Evidence pack | 5–60 MB | Kept forever (only archived) |
| App DB | < 200 MB at hackathon scale | Nightly `pg_dump` in air-gapped mode (§12.11) |

---


# PART 5 — THE SYNTHETIC WORLD (M6 · the generator)

> The PS gives no dataset and says participants will work with "a synthetic dataset modelled on real Bitcoin P2P/transaction fields". The generator is therefore not scaffolding. It is **a core deliverable**, and it is the only thing that lets us *measure* every claim we make. Most teams will download Elliptic and never touch the network layer. We build a world where **both layers exist and the ground truth is known**.

## 5.1 What the generator must prove

1. **Both layers, consistent.** Every transaction has a real originating node. It propagates across a simulated P2P network with Bitcoin-like relay delays, and sensors record what they would really see.
2. **Ground truth for every claim** we will ever grade: who owns every address, which output is change, which transactions are CoinJoins, which are peel hops, which IP and session originated every transaction, and which operations are illicit.
3. **Realism good enough that models transfer.** Checked by automated realism reports (§5.12), and protected by **domain randomisation** (§5.11), so models learn invariances rather than one configuration.
4. **Adversarial range.** Knobs that make criminals harder to catch (§5.7), so we can publish robustness curves instead of one flattering number.
5. **Determinism.** Same scenario and same seed produce byte-identical output. Seeds are threaded through `numpy.random.SeedSequence.spawn` to every component.

## 5.2 World model

| Element | Model | Defaults (hero) |
|---|---|---|
| Clock | Discrete-event simulation over a global heap, microsecond resolution | 21 days |
| Blocks | Poisson arrivals, mean 600 s. Inclusion probability rises with fee rate relative to a congestion curve. | ~3,000 blocks |
| Addresses | **Syntactically valid** mainnet formats from random payloads: base58check (P2PKH `1…`, P2SH `3…`), bech32 (P2WPKH `bc1q…` 42 chars, P2WSH 62 chars), bech32m (P2TR `bc1p…`). Encoders follow BIP-173/BIP-350 reference code. | mix below |
| TXIDs | 32 random bytes (hex). Collisions with real txids are negligible. | – |
| Wallets | Each agent owns ≥ 1 wallet: a UTXO set, an address-generation policy, a coin-selection policy and a **wallet-software fingerprint** (change position, script type, fee rounding, RBF flag) | – |
| Coin selection | `largest_first` · `random_improve` · `single_random_draw` (per wallet software) | mix |
| Change | New address of the same script type as the inputs (default). Position random or fixed per fingerprint. Omitted when the remainder is below dust. | – |
| Fees | Fee rate (sat/vB) from a log-normal with a daily congestion cycle. vsize from standard weights (P2WPKH in ≈68 vB, P2TR in ≈57.5 vB, P2PKH in ≈148 vB; outputs 31/43/34/32/43 vB; ≈10.5 vB overhead) | – |
| Script mix (new addresses) | P2WPKH 55% · P2TR 20% · P2SH 12% · P2PKH 10% · P2WSH 3% `[DEFAULT]` | – |

## 5.3 The benign economy

| Agent type | Count (hero) | Behaviour | Network profile |
|---|---|---|---|
| Retail user | 6,000 | Payments via a Poisson process modulated by a **local diurnal profile** (timezone from country). Log-normal amounts (median ≈ 0.003 BTC). 10% address reuse. Receives from exchanges, pays merchants and users. | NAT'd client on a residential ASN of its country. Some on mobile CGNAT (many clients per IP). |
| Merchant / processor | 150 | Many small inbound payments, periodic sweeps to an exchange | Client or listener on hosting |
| Exchange | 6 (synthetic names `EXA`…`EXF`) | Fresh deposit address per customer. **Sweeps** (big multi-input consolidations, so CIOH absorbs deposits into the exchange cluster). **Batched withdrawals** (many outputs, a CoinJoin false-positive trap). Hot/cold split. | Listeners on hosting ASNs |
| Mining pool | 4 | Coinbase transactions (no inputs), then fan-out payout batches | Listeners on hosting |
| Gambling service | 3 | High-frequency small deposits and withdrawals | Listeners on hosting |
| Payroll / batch payer | 40 | Near-equal outputs to many employees, twice a month (a CoinJoin false-positive trap) | Clients |
| CoinJoin coordinators | 3 styles | **Whirlpool-like:** Tx0 premix, then 5-in/5-out rounds at 0.001/0.01/0.05/0.5 BTC. **Wasabi-like:** ≥ 50 inputs, ≈ 0.1 BTC equal outputs, or multi-denomination WabiSabi-style rounds. **JoinMarket-like:** 2–10 makers plus a taker. **Most participants are benign privacy users.** | Coordinator on hosting; participants from everywhere |

**Mixing is not a crime,** and the world must reflect that. Most CoinJoin users in the generator are benign. The model has to learn that the *combination* (tainted inflow, then mix, then consolidation, then cash-out) is the signal, not the mix alone.

## 5.4 Illicit operations — the typology catalogue

Each operation is a scripted agent with its own wallets, IP behaviour and parameters, all drawn from ranges during randomisation.

| Operation | Script (what it does on-chain) | Key parameters |
|---|---|---|
| **Ransomware** | Victims pay into a fresh address each → **consolidation** (CIOH links them) → **peel chain** (N hops, regular bot-like timing) peeling to **exchange deposit addresses** (cash-out) → remainder into **CoinJoin** (Tx0/premix) → **post-mix consolidation** (a common operator mistake) → exchange or OTC. Infrastructure (VPS, domains) is paid from a **separate wallet W2**, broadcast from the same machine. | victims 5–40 · ransom 0.2–5 BTC · hops 5–40 · hop interval 5–30 min · peel size 3–15% · cash-out services 1–4 · CoinJoin share 0–70% · post-mix mistake p 0–0.6 |
| **Darknet market** | Buyers deposit to per-user market addresses → hot-wallet consolidations → escrow → **batched vendor payouts** (fan-out) → vendors cash out. Admin skims to cold storage. | buyers 200–3,000 · vendors 20–150 · payout cadence daily |
| **Investment scam** | Victims → scam addresses (**fan-in**) → rapid **scatter** to mule wallets → **gather** → exchange | victims 30–400 · mules 5–40 |
| **Laundering typologies** (adapted from AMLSim / AMLworld to UTXO) | **fan-out, fan-in, scatter-gather, gather-scatter, cycle** (round-trip), **stack** (layered bipartite), **random walk**, across wallets the launderer controls or mules | pattern size 3–18 · timing: fixed / random / simultaneous |
| **Mules** | Wallets controlled by an operation but operated from **different IPs and sessions**. The hard case for network correlation. | 0–30 per operation |

**Victims are explicitly modelled.** Ransom payers are benign agents who send money *to* illicit addresses. Backward exposure must not turn them into suspects (`test_victims_not_flagged_as_perpetrators`, §6 E15).

## 5.5 The P2P network

| Element | Model | Defaults (hero) |
|---|---|---|
| Listening nodes | Public IP, port **8333**, accept up to 125 inbound | 1,000 (70% hosting ASNs, 30% residential) |
| Clients | Behind NAT. **Ephemeral source ports** (32768–60999 Linux, 49152–65535 Windows). 8 outbound full-relay peers. | 1,500 clients behind ~900 public IPs |
| NAT / CGNAT | 1–50 clients share one public IP (mobile carriers at the high end) | per-ASN distribution |
| Tor users | Clearnet connections appear from **Tor exit IPs** sampled from the bundled exit snapshot, rotating every ~10 min. A share are **onion-only**: never visible as IPv4, so their broadcasts are **unobservable**. | 4% of benign, op-dependent for illicit |
| VPN users | Connections from IPs in VPN/datacenter ranges (X4BNet lists) | 3% of benign |
| IP assignment | Sampled **inside real ranges** from DB-IP Lite ASN/country CSVs, per category: residential ISPs per country (for India e.g. AS55836 Reliance Jio, AS24560 Bharti Airtel, AS9829 BSNL), hosting (e.g. AS24940 Hetzner, AS16276 OVH, AS14061 DigitalOcean, AS16509 Amazon), VPN, Tor exits. So **enrichment later resolves them to real countries and ASNs.** | country weights: IN 35%, US 15%, EU 20%, rest 30% |
| Sessions | TCP connections persist for hours (log-normal lifetime). Reconnects get new source ports. | – |
| **Relay model (diffusion)** | When node *u* first holds tx at time *tᵤ*, it announces to each peer after an independent exponential delay: **mean ≈ 2 s to outbound peers, ≈ 5 s to inbound peers** (Bitcoin Core inventory-broadcast intervals) `[DEFAULT]`. Add link latency (log-normal by geography, 20–250 ms) and the INV→GETDATA→TX round trip. Arrival time at *v* = min over announcing neighbours. | – |
| Computation | Per transaction: fresh edge delays → single-source Dijkstra (SciPy `csgraph`) over the node graph → first-arrival time at every node. Parallelised across cores. | ~4 min single core; < 1 min on 8 |
| Re-broadcast | An unconfirmed transaction is re-announced by its originator after a random delay (probability rises with time unconfirmed). This is the "re-relay" pattern that Koshy et al. found most revealing. | p grows after 2 blocks |

## 5.6 Observation models — what the sensors actually record

| Model | What is recorded | Records per transaction |
|---|---|---|
| **vantage** | K listening **sensors** (controlled by the observer). Each logs **every INV from each connected peer** for each txid: `(src=peer ip:port, dst=sensor ip:8333, ts, txid, tx fields)`. | ≈ K × (peers-of-sensor that relay it) |
| **flow** | "Taps" covering selected ASNs (e.g. domestic residential ASNs). They record **every tx-carrying message on every link with at least one endpoint in a covered ASN**, in both directions. | Every covered hop |
| **mixed** | Both (the hero default: 40 sensors plus taps on three domestic residential ASNs) | – |

**Measurement imperfections are deliberate.** They are why E09 exists:
- per-sensor clock offset ~ N(0, 50 ms) plus slow drift;
- per-record jitter ~ N(0, 2 ms);
- 1% record loss;
- 0.5% duplicated records;
- occasional out-of-order writes.

## 5.7 Adversary knobs (Adversary mode, R-LAB-003)

| Knob | Range | Makes harder… |
|---|---|---|
| `tor_share` | 0–1 | Origin attribution (exits are shared and rotate) |
| `onion_only_share` | 0–1 | Observability itself (origin becomes unobservable) |
| `vpn_share` | 0–1 | Geo and ASN signal |
| `ip_rotation` | `none` · `per_day` · `per_tx` | Control and co-origin aggregation |
| `mule_count` | 0–30 | Actor resolution |
| `cluster_splitting` | 0–1 | CIOH (the operator avoids co-spending across wallets) |
| `coinjoin_before_cashout` | 0–1 | Taint continuity |
| `postmix_consolidation_prob` | 0–1 | *(lower = harder)* the classic mistake that re-links mixed coins |
| `peel_amount_jitter` | 0–0.5 | The peel scorer's regularity features |
| `peel_timing` | `bot` · `human` · `random` | Timing regularity |
| `timezone_masking` | 0–1 | Behavioural fingerprint (activity spread over 24 h) |
| `fee_mimicry` · `script_mimicry` | 0–1 | Wallet fingerprinting (copies the benign distribution) |
| `decoy_tx_rate` | 0–5 per real tx | Noise in every feature family |

The red-team report (§11.5) sweeps each knob from 0 to max and plots every headline metric. **We publish where the system breaks.**

## 5.8 Ground truth outputs

```
worlds/<name>/
├── data/                       # what the SYSTEM sees (the exported dataset)
│   ├── traffic.csv | traffic.json | traffic.ndjson | traffic.xml   (+ variants)
│   └── watchlist.csv           # PARTIAL seeds handed to the system (e.g. 3 of 12 ransom addresses)
├── truth/                      # what ONLY sutradhar_evals may read (I7)
│   ├── agents.parquet          # agent_id, type, illicit, operation_id, country, tz, wallet_ids
│   ├── addresses.parquet       # address → agent_id, wallet_id, is_change, deposit_of (service, customer)
│   ├── txs.parquet             # txid → sender agent, operation_id, is_coinjoin+kind, change_out_idx,
│   │                           #        peel_chain_id+hop, typology, is_victim_payment
│   ├── ips.parquet             # ip → node_ids, kind (residential/hosting/tor_exit/vpn), is_nat, clients
│   ├── origins.parquet         # txid → origin node, origin ip, origin session, observable (bool)
│   ├── sensors.parquet         # sensor ip, kind, true clock offset
│   ├── operations.json         # story-level truth: members, cash-out services, narrative
│   └── arrivals.npz            # optional: arrival times at ALL nodes for a tx sample (sensor planner)
└── world.json                  # scenario, seed, every parameter and knob, generator version
```

## 5.9 Exporters and schema variants

The **canonical** exporter writes exactly the PS minimum fields plus optional extras, in CSV, JSON, NDJSON and XML (R-PS-15). **Variant** exporters exist to break our own ingestion before NTRO does:

| Variant | Change |
|---|---|
| `renamed` | Vendor-style names (`tx_hash`, `source.ip`, `vin_addrs`…) and shuffled column order |
| `units_btc` / `units_sat` | Decimal BTC vs integer satoshis |
| `time_epoch_ms` / `time_iso_ist` | Epoch milliseconds vs ISO-8601 with a `+05:30` offset |
| `arrays_delimited` / `arrays_indexed` | `a;b;c` in one cell vs `input_address_0…n` columns |
| `no_fee` · `no_script` · `per_io_script` | Missing optional fields / per-input script types |
| `xml_nested` / `xml_wrapped` | `<input><address/><amount/></input>` vs `<input_addresses><address/>…` |
| `noisy` | Extra irrelevant columns, CRLF line endings, BOM, gzip |
| `single_obs` | One record per transaction (tests the `single` observation model) |

`schema-zoo` generates all variants of one world. `test_three_formats_same_digest` and `test_variants_same_digest` assert that every variant normalises to the **same** `normalised_digest`.

## 5.10 Scenario packs

| Pack | Purpose | Size | Distinctive settings |
|---|---|---|---|
| `tiny` | CI and unit tests: runs in seconds | ~2 k tx · ~50 k obs | One of each operation, 8 sensors |
| **`hero-ghostline`** | **The demo** | ~60 k tx · ~1.5 M obs | Specified below |
| `bazaar` | Second demo thread: darknet market | ~40 k tx | Market plus vendors cashing out |
| `benign-heavy` | False-positive stress | ~60 k tx | Heavy exchange batching, payroll, privacy CoinJoins, no illicit cash-out |
| `tor-heavy` · `onion-only` | Network-evasion stress | ~30 k tx | `tor_share` 0.6, `onion_only_share` 0.3 |
| `sparse-sensors` | Coverage stress | ~30 k tx | 6 sensors, no taps |
| `nat-crowded` | Shared-IP stress | ~30 k tx | Mobile CGNAT, 50 clients/IP |
| `coinjoin-heavy` | Mixing stress | ~40 k tx | 25% of volume through coordinators |
| `flow-isp` | Flow observation model | ~30 k tx | Taps only, no vantage sensors |
| `schema-zoo` | Ingest robustness | ~5 k tx | All variants (§5.9) |
| `academy-01…05` | Training challenges | ~10 k tx | One hidden story each, with a question set |
| `train-rand` · `val-rand` · **`test-rand`** | Model training and honest evaluation | 40 / 10 / 10 worlds | Domain-randomised (§5.11). `test-rand` seeds are frozen and **never** used for tuning. |

### 5.10.1 The hero scenario — *Operation GHOSTLINE*

The demo is designed backwards from the story we want the product to reveal. Every number below is a **generator target**. The numbers shown on stage are whatever the engine actually finds, and the evaluation report states them.

- **World.** 21 days · ~2,500 nodes · 40 vantage sensors plus flow taps on 3 domestic residential ASNs · 6,000 retail users · 6 exchanges · 4 pools · 3 gambling services · 3 CoinJoin styles · a darknet market (background thread) · two scams · a laundering ring.
- **GHOSTLINE (ransomware).**
  - **Victims.** 12 victims, including a hospital, pay 0.4–2.5 BTC each (≈ 14 BTC) to 12 fresh addresses.
  - **Watchlist.** Only **3 of the 12** ransom addresses are on the watchlist handed to the system.
  - **Consolidation.** All 12 are co-spent into one address, so CIOH links them.
  - **Peel chain.** 23 hops at **bot-regular intervals (9–15 min)**, peeling 0.2–0.6 BTC to **11 deposit addresses at 3 exchanges** (EXB, EXD, EXE).
  - **Mixing.** The remaining ~5 BTC enters a Whirlpool-like 0.05 BTC pool.
  - **The mistake.** A **post-mix consolidation** of 20 outputs (the operator's mistake), then a deposit at EXD.
- **The operator's machine.** A client behind NAT on **AS55836 (Reliance Jio)**, plus a second on **AS24560 (Bharti Airtel)**.
  - Activity follows **IST (UTC+05:30)**, 10:00–02:00.
  - 30% of broadcasts go via **Tor exits**.
  - A **second wallet W2** (no on-chain link to the ransom funds) pays for infrastructure and is broadcast from **the same TCP sessions**, which is the co-origin link the engine should find.
- **What a good run shows on stage:**
  - lead #1 is the GHOSTLINE actor, **grade A**, with families NET, FLOW, TAINT and BEHAV;
  - W2 is merged into the actor through co-origin;
  - three **CASHOUT** leads at EXB, EXD and EXE;
  - one **CHAIN** lead of 23 hops;
  - the origin IPs on Jio and Airtel with IST activity;
  - the victims listed as *victims*, not suspects.

## 5.11 Domain randomisation (how models avoid overfitting our world)

Every training world samples its parameters from ranges, never from the hero defaults:

| Group | Randomised ranges |
|---|---|
| Network | nodes 1,000–5,000 · sensors 5–80 · taps 0–4 ASNs · outbound degree 8 ± 2 · INV mean delays 1–6 s (outbound) / 2–10 s (inbound) · latency scale ×0.5–×2 |
| Population | NAT sharing 1–50 · Tor 0–40% · VPN 0–20% · onion-only 0–50% of Tor |
| Economy | agent counts ×0.3–×3 · script mix Dirichlet around defaults · fee regime calm/congested · address reuse 0–30% |
| Operations | every parameter in §5.4 over its full range · all adversary knobs 0–max with p = 0.5 each |
| Measurement | skew σ 0–200 ms · loss 0–5% · duplicates 0–2% |

**Splits are by world, never by row.** A model is evaluated only on worlds it has never seen. This removes the leakage that makes Elliptic papers look better than they are (a random row split lets a model memorise neighbours).

## 5.12 Realism checks

`sutradhar gen validate <world>` produces a report. Out-of-range checks are **flagged, not fatal**: realism is a spectrum, and hiding a weak spot would be worse.

| Check | Target band `[DEFAULT]` | Basis |
|---|---|---|
| Inputs/outputs per tx | Most txs have 1–2 inputs and 2 outputs; a heavy tail of large batches | Common knowledge of the Bitcoin tx distribution |
| UTXO waiting time | Heavy-tailed, median well below mean | Power-law waiting times reported for Bitcoin (arXiv 2309.11884) |
| Address reuse | 5–30% of addresses receive more than once | – |
| Script-type mix | Segwit-v0 majority, rising P2TR share | Configured mix ± 5 points |
| Propagation | 50% of nodes reached within a few seconds, 90% within ~10–20 s | Diffusion delays as configured |
| Degree distribution | Heavy-tailed entity degree (exchanges as hubs) | – |
| CoinJoin share | Configured share ± 20% | – |
| Label balance | Illicit actors 0.5–3% of actors | Elliptic-like imbalance (~2% illicit) |

## 5.13 Generator architecture and CLI

```
packages/generator/sutradhar_gen/
├── world.py            config, SeedSequence tree, event heap, clock, blocks
├── addresses.py        valid-format address factory (base58check, bech32, bech32m)
├── economy/            wallets, UTXO sets, coin selection, change, fees, vsize
├── agents/             user, merchant, exchange, pool, gambling, payroll, coinjoin coordinators
├── ops/                ransomware, darknet_market, scam, laundering (typologies), mules
├── net/                topology (nodes, peers, NAT, Tor, VPN), ipspace (real ranges), propagate (Dijkstra, mp)
├── observe.py          vantage / flow / mixed · skew · jitter · loss · dupes · rebroadcast
├── truth.py            truth writers (Parquet/JSON)
├── export/             canonical + variants (csv, json, ndjson, xml)
├── scenarios/*.yaml    pack definitions (hero-ghostline.yaml, …)
└── realism.py          checks + report
```

```bash
sutradhar gen run      --scenario hero-ghostline --seed 2026 --out worlds/hero --formats csv,json,xml
sutradhar gen run      --scenario schema-zoo --seed 7 --out worlds/zoo --variants all
sutradhar gen randomize --count 40 --seed-base 1000 --out worlds/train     # train-rand
sutradhar gen validate worlds/hero                                          # realism report
```

**Performance target:** `hero-ghostline` in ≤ 10 minutes on the reference 8-core laptop. Propagation is the hot loop and is parallelised; everything else is vectorised NumPy.

---


# PART 6 — THE ANALYTICS ENGINE, STAGE BY STAGE (M1 + M2)

> Every stage below states its **purpose, algorithm, defaults, outputs, guards and tests**. Defaults are settings (`[DEFAULT]`, §17.3), never constants in code. Stage code lives in `packages/engine/sutradhar_engine/stages/eNN_<name>.py`. Each stage is a pure function `run(ctx: RunContext) -> StageReport`.

## 6.0 The run context and the stage contract

```python
# packages/engine/sutradhar_engine/context.py
@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_db: duckdb.DuckDBPyConnection  # read-write until E19, then closed
    dataset_db_path: Path  # ATTACHed read-only as 'ds'
    settings: Settings  # frozen snapshot, hashed into the manifest
    models: ModelBundle  # loaded, versioned, sha-checked artefacts
    refdata: RefData  # mmdb readers + CIDR sets, versioned
    capability: CapabilityProfile  # from I06; decides which stages/features run
    rng: np.random.Generator  # child of SeedSequence(settings.seed)
    threads: int  # fixed for determinism (I4)
    progress: Callable[[str, float, dict], None]  # → job_events → SSE


@dataclass
class StageReport:
    stage: str
    ms: int
    rows: dict[str, int]
    notes: list[str]
```

**The stage contract:**
- **Inputs.** A stage reads only tables written by earlier stages (declared in `REQUIRES`) and writes only its own (declared in `PRODUCES`). `test_stage_contracts` checks this against the DuckDB catalogue.
- **Determinism.** Every write is preceded by an explicit `ORDER BY`, and all randomness comes from `ctx.rng`.
- **Resumability.** After each stage the runner commits and records `runs.stage`. A failed run resumes from the last completed stage.

## 6.1 Ingestion (I01–I06) — per dataset

| Stage | Algorithm | Defaults | Guards |
|---|---|---|---|
| **I01 read** | Format sniffing (magic bytes, first non-space character, extension) → streaming reader. Batches of 100 k records. **Memory is bounded regardless of file size.** | batch 100 k | Upload cap (demo 25 MB, airgap none). Decompression ratio ≤ 200:1. Record ≤ 1 MB. Nesting depth ≤ 32 (V20). |
| **I02 map** | Apply the confirmed mapping profile. If none exists, the **auto-mapper** proposes one from a 1,000-row sample (name synonyms plus value-shape detectors) and the dataset stops at `MAPPED` for confirmation. In CLI and auto mode it proceeds when every required field has ≥ 0.9 mapping confidence. | auto-accept ≥ 0.9 | Unknown columns preserved in `extras`, never dropped silently |
| **I03 normalise** | Units → satoshis via `Decimal` (I9). Time → UTC µs (I10). IPs canonicalised. Arrays aligned. Script type inferred (§4.3.3). Txid lowercased. | – | Float-free money path; `test_no_float_money` |
| **I04 validate** | Rules V01–V20 (§4.4), vectorised in Polars | reject-rate hold 20% | Rejects written with rule and value |
| **I05 reconcile** | Deduplicate exact rows (V11). Group by txid and compare content hashes; mismatches are quarantined (V10). `tx`, `txin` and `txout` come from the first valid observation. | – | Conflicting variants stored for the X-ray |
| **I06 profile** | Capability profile and X-ray (§4.5), including observation-model detection | – | Always completes, even at 100% rejects, so the analyst sees *why* |

## 6.2 E01 `load`

- **Purpose.** Freeze the run's view of the world.
- **Algorithm.** `ATTACH 'dataset.duckdb' AS ds (READ_ONLY)`. Build dense dictionary tables `d_tx`, `d_addr` and `d_ip` by sorting natural keys and assigning `ROW_NUMBER()` (deterministic). Snapshot the **watchlist** (items and version) into `seed_input` and the **analyst assertions** (`merge_decisions`) into `assertion_input`. Later edits to either never change this run (I4).
- **Output.** `d_*`, `seed_input`, `assertion_input`, `run_meta.capability`.
- **Tests.** `test_dims_dense_and_sorted`, `test_capability_disables_net_stages` (a chain-only dataset skips E09–E11 and marks NET features missing).

## 6.3 E02 `enrich`

- **Purpose.** Everything we can know about an IP without asking the internet.
- **Algorithm.**
  1. **Lookups.** DB-IP country and ASN lookups through `maxminddb` readers (memory-mapped).
  2. **Tor exit.** Exact membership in the bundled exit-list snapshot.
  3. **VPN / hosting.** CIDR membership in the X4BNet VPN and datacenter lists, via sorted integer intervals and bisect.
  4. **Bogon.** RFC 1918, 100.64/10, 127/8, 169.254/16, fc00::/7, ::1 and similar.
  5. **Role inference.**
     - `listener`: seen as source with port 8333, or receiving inbound from ≥ 2 distinct peers on 8333.
     - `client`: only ephemeral source ports.
     - `sensor`: detected from the traffic pattern (a destination IP whose distinct-source in-degree is in the top 1% **and** that observes ≥ 50% of txids), or labelled explicitly by `sensor_id`.
- **Provenance.** Every enrichment value records `refdata_version` (for example `dbip-asn-lite@2026-09`) (I20).
- **Output.** `ip_enrich`, `sensor`.
- **Tests.** `test_geoip_offline_lookup`, `test_tor_exit_flag`, `test_role_inference` (tiny world, compared with truth).

## 6.4 E03 `flows` — rebuilding the money graph without prevouts

- **Purpose.** Transaction → transaction money flow, which peel chains, taint and flow motifs all need.
- **Key insight** `[DECISION]`. The PS minimum fields have no `prevout`, but they **do** have `input_amounts[]` aligned with `input_addresses[]`. A spent output is the pair *(address, exact satoshi amount)* created earlier, so **(address, amount) matching reconstructs the UTXO graph** almost exactly.
- **Algorithm.**
  1. When `input_prevouts` exist, link exactly (`method = prevout`, confidence 1.0).
  2. Otherwise, for each input `(A, v, t_spend)`, find candidate outputs `(A, v)` created before `t_spend` that are not yet matched. Candidates are ordered by creation time; assign greedily in spend-time order (the earliest unspent candidate). If *k* equally valid candidates remain, confidence = 1/k (`method = addr_amount_match`).
  3. Inputs with no candidate are **external funding** (created outside the dataset window). They are marked, never guessed.
  4. Also record `utxo_spend (tx_i, out_idx, spent_by, dt_us)`, the UTXO age features.
- **Implementation.** DuckDB join on `(address, sats)` with window ranks; Python resolves only the rare multi-candidate groups.
- **Output.** `flow` (envelope), `utxo_spend`.
- **Tests.** `test_prevout_exact_links`, `test_addr_amount_match_recovers_truth` (≥ 0.99 precision and recall on `tiny`), `test_external_inputs_marked`.

## 6.5 E04 `coinjoin`

- **Purpose.** Score every transaction for mixing structure. This runs *before* clustering, because CoinJoins are the main source of wrong common-input merges (Kappos et al. 2022; GraphSense documentation).
- **Features (per tx):**
  - counts: `n_in`, `n_out`, distinct input/output addresses;
  - equal-output structure: `max_equal_out` (size of the largest equal-value output group), `n_equal_groups`, `equal_out_ratio`;
  - denominations: `denom_whirlpool` (exact 0.001/0.01/0.05/0.5 BTC), `denom_wasabi1` (0.1 ± 0.02 BTC), `in_eq_denom` (remix inputs equal to the pool size), `in_near_denom` (inputs in [pool, pool + 0.0011 BTC]);
  - value shape: output value entropy, `out_value_cv`, `max_out_share`, output/input ordering flags;
  - scripts and reuse: script-type uniformity (inputs and outputs), address-reuse ratio;
  - `in_out_ratio`, and fee rate when `vsize` is present.
- **Rule features.** The published heuristics as booleans, **used as features, not verdicts**:
  - Whirlpool: 5 in and 5 out, all outputs equal to a pool size, 1–3 remix inputs;
  - Wasabi-1: ≥ 10 outputs at 0.1 ± 0.02, inputs ≥ the equal count;
  - WabiSabi-like: ≥ 10 inputs and outputs, ≥ 3 equal-value groups;
  - JoinMarket-like: ≥ 2 equal outputs, change present, distinct addresses;
  - generic: ≥ 5 equal outputs (Stütz et al. 2022; Gavenda et al. 2025; the BlockSci fork).
- **Model.** `coinjoin_clf`, multi-class LightGBM over `{none, whirlpool_like, wasabi_like, joinmarket_like, generic, batch_payout}`. **`batch_payout` is an explicit class**, so exchange batches and payroll stop being called mixes. `p_coinjoin` = the sum of the four mixing classes.
- **Defaults.** τ_cj = 0.5.
- **Output.** `cj`.
- **Tests.** `test_coinjoin_f1` (≥ target, §11.3), `test_batch_payout_not_coinjoin`, `test_rule_features_on_reference_shapes`.

## 6.6 E05 `cluster` — common-input ownership, safely

- **Purpose.** Group addresses spent together (R-PS-10, first half).
- **Algorithm.**
  1. **Edges.** For each transaction with ≥ 2 inputs, `p_coinjoin < τ_cj` (I8) and not quarantined, add a star edge from the first input (sorted) to every other input.
  2. **Components.** `scipy.sparse.csgraph.connected_components` over `addr_i`. Components are relabelled by their minimum `addr_i`, so entity IDs are deterministic.
  3. **Mega-cluster inspection.** A component is flagged `suspect_mega` if it is larger than `S_max` = max(5,000, 50 × the p99 cluster size) `[DEFAULT]`, or if it contains transactions with borderline `p_coinjoin` ∈ [0.3, τ_cj). The borderline transactions inside it are then removed and components recomputed. If the component splits into ≥ 2 components of ≥ 50 addresses, the split is kept and `split_reason` is recorded.
- **Envelope.** `method = cioh`, confidence 1.0, `heuristic = true`. The UI always labels CIOH membership as *heuristic* (Müller et al. 2026).
- **Output.** `entity`, `entity_member`.
- **Tests.** `test_cioh_excludes_coinjoin` (I8), `test_cluster_ids_deterministic`, `test_mega_cluster_split`. Per-wallet precision and recall are reported by the evaluation harness.

## 6.7 E06 `change`

- **Candidates.** Non-CoinJoin, non-coinbase transactions with 2 ≤ n_out ≤ 4 `[DEFAULT]`.
- **Features (per output):**
  - script-type match with the inputs;
  - address **fresh** here (first ever appearance) · address reused later;
  - **round-amount score** (trailing zero digits of the BTC value);
  - value rank and value/input ratio;
  - output index and last-index flag;
  - time until spent;
  - **later co-spent with the sender's entity** (strong);
  - later spent by a transaction with the same wallet fingerprint.
- **Model.** `change_clf`, binary LightGBM. Per transaction, the arg-max output is the change if p ≥ 0.5.
- **Merge policy.** Add the change address to the sender's entity only if **p ≥ 0.95** `[DEFAULT]`, the transaction is not a CoinJoin, and the entity is not `suspect_mega` (`method = change_model`, confidence = p).
- **Output.** `change_link`, extra `entity_member` rows.
- **Tests.** `test_change_precision_at_merge_threshold`, `test_change_merge_respects_coinjoin`.

## 6.8 E07 `peel` — peel chains

- **Start.** Transactions with 1–2 inputs and 2 outputs, one of them predicted change (p ≥ 0.5) and the other ≥ 3× smaller (the "peel").
- **Traverse.** Follow the change output to its spending transaction (via `utxo_spend`) while the peel shape holds. Stop at a CoinJoin, an unspent output, a shape break, or **200 hops**.
- **Chain features:**
  - `n_hops`;
  - inter-hop time mean, standard deviation and **coefficient of variation** (bots are regular);
  - peel-ratio mean and standard deviation;
  - amount-decay slope;
  - script, fee and fingerprint consistency;
  - distinct peel-destination entities;
  - share of peels landing at **services**;
  - chain duration and hour-of-day spread.
- **Model.** `peel_scorer`, LightGBM. **Laundering chains** (from operations) are positives. **Benign peel-like sequences** (exchange hot wallets paying withdrawals one by one, users spending down) are negatives. The scorer includes its own isotonic calibration.
- **Output.** `peel_chain`, `peel_hop`, `PEEL_NEXT` edges. A **CHAIN** lead is raised when p ≥ 0.6 and n_hops ≥ 3 `[DEFAULT]`.
- **Tests.** `test_peel_chain_recall_5plus_hops`, `test_exchange_payout_chain_not_flagged`.

## 6.9 E08 `motifs` — laundering typologies (as plugins)

- **Graph.** An entity-level flow graph per sliding window (24 h and 72 h) `[DEFAULT]`, aggregated from `flow`: value, count, first and last time.
- **Built-in detectors** (each is a plugin on the public SDK):

| Detector | Definition (window W) | Output |
|---|---|---|
| `fan_out` | Entity pays ≥ k distinct entities (k = 5) | surprise score vs the entity's own history and the population |
| `fan_in` | Entity receives from ≥ k distinct entities | ditto |
| `scatter_gather` | A → {B₁…B_k} → C with ≥ 60% of A's outflow reaching C | members, conserved-value share |
| `gather_scatter` | ≥ k in → hub → ≥ k out, hub dwell < 24 h | members |
| `cycle` | Simple cycle of length 3–6 returning ≥ 50% of value within 7 days | cycle, value share |
| `stack` | Two bipartite layers moving ≥ 60% of value | layers |
| `pass_through` | k-hop chain forwarding ≥ 90% of value with dwell < 2 h per hop | chain |

- **Use.** Motif hits are ranker features and explanation material. Only `cycle`, `scatter_gather` and `pass_through` can raise **standalone** CHAIN leads. Fan patterns are how services behave, so on their own they would drown the queue.
- **The SDK.**

```python
# packages/engine/sutradhar_engine/sdk.py  (public, semver-stable)
class Detector(Protocol):
    id: str  # "scatter_gather"
    version: str  # "1.0.0"
    family: Family  # FLOW | NET | BEHAV | ANOM | TAINT
    requires: frozenset[str]  # e.g. {"flow", "entity_member"}
    Params: type[BaseModel]  # validated from settings: detectors.<id>.*

    def run(self, ctx: RunContext, params: BaseModel) -> Iterable[MotifHit]: ...
    def reason(self, hit: MotifHit) -> ReasonArgs: ...  # fills a hedged template


# discovery: Python entry points group "sutradhar.detectors" + /plugins directory (airgap)
```
- **Tests.** One golden mini-world per detector (hand-built, known answer) plus `test_plugin_sdk_contract`.

## 6.10 E09 `timing` — clock skew and sessions

- **Clock skew.** For each sensor *s*, take the median over txids of (s's first observation − the median first observation across the other sensors), minus the population median of that quantity. Apply the correction only when |offset| > 3× its bootstrap CI.
  - `[DECISION]` The origin features lean on **within-sensor ranks**, which are *invariant* to a sensor's constant clock offset. Skew correction only matters for the cross-sensor comparisons.
- **Sessions.** Group observations by `(src_ip, src_port)` for ephemeral ports. A session is a maximal run with gaps < 30 min `[DEFAULT]`. Listener announcements (source port 8333) cannot be split into sessions and are flagged `listener_session`.
- **Output.** `sensor.skew_us`, `sensor.skew_ci_us`, `session`, and the `obs → sess_i` map.
- **Tests.** `test_skew_estimate_correlates_with_truth` (r ≥ 0.9 where |true skew| ≥ 50 ms), `test_sessions_split_on_gap`.

## 6.11 E10 `origin` — the centrepiece (R-PS-03)

**Question.** For each transaction: which observed endpoint most likely *created* it, and how likely is it that the true creator was **not observed at all**?

**Candidates.** Up to 20 `[DEFAULT]` earliest distinct `(ip, session)` sources that relayed the transaction (vantage). In the flow model, every node that sent it.

**Features per (transaction, candidate):**

| Group | Features |
|---|---|
| Timing | `dt_first_s` (skew-corrected, relative to the transaction's first observation) · `rank_global` · `min_rank_within_sensor` · `mean_rank_within_sensor` · `frac_sensors_first` (share of observing sensors where this candidate announced first) · `n_sensors_reached` · `n_obs` |
| Relayer base rates (hub correction) | `cand_first_rate` (how often this candidate is first for *any* transaction) · `cand_relay_volume` · `cand_sensor_degree`. Well-connected relays are often first without being the origin; these features let the model discount them. |
| Role and infrastructure | `is_listener` · `is_client` · `is_tor_exit` · `is_vpn` · `is_hosting` · `is_bogon` |
| Re-broadcast (Koshy) | `rebroadcast_count` (announced again ≥ 10 min after first) · `rebroadcast_gap_s` |
| Flow model | **`sent_before_received`** (sent it before any observed receipt) · `n_prior_receipts` · `fanout_first_second` · `in_covered_asn` |
| Consistency (pass 2) | `sess_prior_origin_same_entity`: this session originated other transactions whose inputs belong to the same entity |
| Transaction context | `n_cand` · `n_sensors_obs_tx` · `tx_spread_s` · `tx_n_in` |

**Model.** `origin_ranker` is a bundle of two boosters:
1. **`pair_booster`**: binary LightGBM on (transaction, candidate) pairs. Its logits are soft-maxed per transaction into shares.
2. **`observable_booster`**: transaction-level, P(the true origin is among the candidates).

P(candidate) = P(observable) × share. **P(unobservable) = 1 − P(observable).** The top-1 probability is isotonic-calibrated on validation worlds.

**Two passes.** Pass 1 runs without consistency features. E11 then aggregates control. Pass 2 recomputes with `sess_prior_origin_same_entity`. There are exactly two passes (determinism and runtime).

**Baselines that must be beaten (published):**
- **first-spy:** the arg-min of skew-corrected first observation;
- **first-sender** (flow model): the earliest node with `sent_before_received`.

The theory backs a learned, structure-aware estimator: Fanti & Viswanath (NeurIPS 2017) show that under Bitcoin's diffusion the first-timestamp estimator's detection probability *decays* with node degree, while likelihood-based estimators stay high.

**Output.** `origin_cand` (features and p), `origin` (arg-max, `p_top`, `p_unobservable`, envelope), and `ORIGINATED` edges for the top 3 with p ≥ 0.2 `[DEFAULT]`.

**Tests.** `test_origin_beats_first_spy` (on `test-rand`), `test_origin_calibration_ece`, `test_unobservable_detected` (onion-only broadcasts get high `p_unobservable`).

## 6.12 E11 `control` — from "who sent this transaction" to "who controls this wallet"

- **Control.** P(session *s* controls entity *e*) = **1 − Π(1 − pᵢ)** over transactions *i* spending *e*'s addresses with `ORIGINATED(s, i) = pᵢ` (noisy-OR). IP-level control is aggregated the same way over the IP's sessions.
- **Crowdedness.** The number of entities an IP controls with p ≥ 0.5. NAT, CGNAT, services and Tor exits are crowded, so IP-level evidence is weighted by **1 / log₂(1 + crowd)** (IDF). **Session-level evidence is not down-weighted.** One TCP connection is one machine.
- **Co-origin.** strength(a, b) = Σ over shared sessions min(p_a, p_b) + Σ over shared IPs min(p_a, p_b) × IDF. A `CO_ORIGIN` edge is written when strength ≥ 0.5 `[DEFAULT]`. **Tor, VPN and hosting IPs never create co-origin edges on their own** (a Tor exit is shared by thousands).
- **Output.** `control`, `co_origin`.
- **Tests.** `test_control_links_calibrated`, `test_tor_exit_not_co_origin`, `test_session_beats_ip_under_nat`.

## 6.13 E12 `embed` — graph embeddings (R-PS-10, second half)

- **Graph.** Entities as nodes. Edges are symmetric weights w = log(1 + sats) + 0.5 × log(1 + count) from money flow only. Co-origin is deliberately excluded, so embeddings stay an **independent** signal.
- **Algorithm.** Normalised adjacency D^−½ A D^−½, then `randomized_svd(k = 32, n_iter = 5, random_state = seed)`. The embedding is U·√Σ, L2-normalised. Isolated entities get the zero vector.
- **Output.** `embedding`.
- **Tests.** `test_embedding_deterministic`. The evaluation reports same-owner precision@10 of the k-nearest neighbours against random.

## 6.14 E13 `resolve` — entities into actors

- **Blocking (candidate pairs, capped at 200 k):**
  - (a) shared session with co-origin ≥ 0.2;
  - (b) shared low-crowd IP (crowd ≤ 5);
  - (c) embedding k-nearest neighbours (top 10, cosine ≥ 0.8);
  - (d) a change link with 0.5 ≤ p < 0.95 between them;
  - (e) peel-chain adjacency.
- **Features:**
  - co-origin strength, shared sessions, shared IPs (IDF);
  - embedding cosine;
  - **timezone-histogram similarity** (1 − Jensen–Shannon);
  - active-day Jaccard, counterparty Jaccard;
  - fee-rate profile similarity, script-mix similarity, round-amount preference similarity;
  - change-link p, peel adjacency, size ratio, both-Tor-heavy.
- **Model.** `er_pair_clf`, LightGBM giving p_same.
- **Decisions** (§2.7):
  1. **Analyst assertions first.** `accept` forces a merge; `reject` is a cannot-link, and union-find refuses any merge that would join a rejected pair.
  2. **Auto-merge** at p ≥ 0.90 when neither side is CoinJoin-contaminated.
  3. **Suggestions** at 0.60–0.90.
- **Actors.** Connected components of the merges.
- **Output.** `er_pair`, `actor`, `actor_member`.
- **Tests.** `test_er_improves_per_wallet_recall` (at ≤ 2 points precision cost), `test_rejected_assertion_never_merged`, `test_accepted_assertion_always_merged`.

## 6.15 E14 `services` — and the victims

- **Service score** (weighted heuristic `[DEFAULT]` in v1; a learned version is `[STRETCH]`):
  - distinct counterparties in and out;
  - deposit-sweep structure (many single-use addresses swept together);
  - batch-payout frequency;
  - **flat 24-hour activity** (high hour-of-day entropy);
  - coinbase receipts (pool) or coordinator-fee receipts (mixer);
  - hosting or listener network profile.
- **Type guess.** Rules: pool, mixer, exchange, gambling, merchant, unknown.
- **Services are never ACTOR leads.** They are where CASHOUT leads live.
- **Victims.** `exposure_out` is the value an actor *sent to* seed-linked actors. An actor with exposure out, no tainted inflow and a benign profile gets **`victim_like = true`**. It is excluded from ACTOR leads and listed in the case as a probable victim.
- **Output.** `service`, and `risk.victim_like` flags.
- **Tests.** `test_exchange_detected_as_service`, `test_victims_not_flagged_as_perpetrators`.

## 6.16 E15 `risk` — propagating risk from seed wallets (R-PS-13)

**Seeds.** Watchlist addresses from the E01 snapshot, each with category and confidence. A seed's CIOH entity inherits seed status at membership confidence.

**1. Haircut taint, forward, in time order.** For every transaction T:
```
taint_frac(T)     = Σ_inputs taint_sats(i) / in_sats(T)
taint_sats(out o) = taint_frac(T) × sats(o) × δ          δ = 0.9 per hop  [DEFAULT]
```
- **Services** receive taint (for CASHOUT) but **do not pass it on**, because they pool everyone's money `[DEFAULT: stop]`. Without this stop, poison and haircut taint spread to most of the network within a few years ("Tendrils of Crime", 2019).
- **CoinJoins** dilute taint proportionally. Post-mix consolidation re-concentrates it at entity level, which is exactly how the GHOSTLINE mistake becomes visible.
- **Cut-offs:** max 40 hops; fractions below 10⁻⁴ are dropped.

**2. Personalized PageRank** on the actor flow graph (directed; weights = share of the source's outflow). The reset vector sits on seed actors in proportion to seed confidence, with damping 0.85 (igraph `personalized_pagerank`). Reported as a raw score and a percentile.

**3. k-best paths.** For the top 500 risky actors, the 3 best seed → actor paths maximising the product of edge taint fractions (Dijkstra on −log w). They are stored with their transaction references as the **Path to seed** explanation.

**CASHOUT candidates.** Service-owned deposit addresses with taint ≥ 0.05 BTC **and** taint fraction ≥ 0.2 `[DEFAULT]`.

**Output.** `risk` (`taint_frac_in`, `taint_sats_in`, `ppr`, `hops_to_seed`, `exposure_out`, `victim_like`), `risk_path`, `TAINT_PATH` edges.

**Tests.** `test_taint_conserves_value` (total taint ≤ seed value), `test_taint_stops_at_services`, `test_ppr_deterministic`, `test_paths_valid` (every path edge exists in `flow`).

## 6.17 E16 `anomaly` (R-PS-11)

- **Transaction level.**
  - value: log value, output roundness;
  - fees: fee-rate z-score within its 6-hour window;
  - shape: `n_in`, `n_out`, output-value entropy;
  - input UTXO age;
  - **hour-of-day deviation from the sender's own timezone profile**;
  - script-mix novelty for the sender.
- **Actor level.**
  - volume and velocity;
  - burstiness (CV of inter-transaction times);
  - **dormancy-then-burst**;
  - fan ratios and counterparty diversity;
  - share of value through CoinJoins.
- **Model.** `anomaly_iforest`: two `IsolationForest(n_estimators = 300, random_state = seed)` models, one per level. Scores are rank-normalised to percentiles.
- **Output.** `anomaly`.
- **Tests.** `test_anomaly_scores_injected_outliers_high` (injected outliers land in the top 5%).

## 6.18 E17 `rank` — leads

1. **Feature assembly.** Build `feat_actor` (~70 named features, grouped by family; §7.3.7).
2. **Score.** `lead_ranker` (LightGBM) → raw score → **isotonic calibration** → p. The same model package carries a second calibrator for CASHOUT p, fitted on validation worlds against "this deposit belongs to an illicit customer".
3. **Drift.** Population Stability Index per feature against the training histograms stored in the model card, written to `drift` (§7.6).
4. **Generate leads:**
   - **ACTOR:** p ≥ 0.40, not a service, not `victim_like`.
   - **CASHOUT:** from E15, with calibrated p.
   - **CHAIN:** from E07/E08 (the scorer's own calibration).
   - **TX:**
     - CoinJoin entries and exits carrying ≥ 20% taint;
     - anomalous transactions (≥ 99.5th percentile) touching risky actors;
     - **watchlist hits.** These are labelled `rule`, never `model`, and their p = the seed's confidence.
   - **IP:** endpoints controlling an ACTOR lead with p ≥ 0.6. Tor, VPN and hosting IPs appear as *context*, not as IP leads.
5. **Families, grade, priority** per §2.5, and `lead_key` per §4.8.

- **Tests.** `test_every_lead_has_reason_grade_calibrated_p` (I6), `test_services_never_actor_leads`, `test_priority_formula`.

## 6.19 E18 `explain`

Specified fully in Part 8. In short:
- **Reasons.** TreeSHAP contributions via LightGBM `pred_contrib=True`: the top 6 supporting and top 2 opposing, mapped to hedged templates.
- **Counterfactual.** A greedy counterfactual to below the grade threshold.
- **Evidence subgraph.** At most 150 nodes, every edge with its envelope.
- **Timezone profile.** Offset and confidence from a 24-bin activity histogram, for actors with ≥ 20 transactions.

## 6.20 E19 `publish`

1. **Validate invariants** on run tables (I2, I6). Any violation fails the run. A partial publish is worse than none.
2. **Digests.** Table digests, then the **result digest**. Write the manifest (§4.10).
3. **Freeze.** `CHECKPOINT`, close, `chmod 0444` on `run.duckdb` (I3).
4. **Publish.** Insert lead summaries into the app DB in one transaction and **carry lead state forward** by `lead_key`:
   - new keys start `NEW`;
   - existing keys update `last_seen_run_id`;
   - `changed_since_review` is set when grade or priority moved by more than 20%.
5. **Diff** against `prev_run_id`: new, changed and gone. Watchlist hits are emitted instantly.
6. **Notify.** SSE `run.published` and audit `run.published`.

- **Tests.** `test_completed_run_is_read_only` (I3), `test_run_is_deterministic` (I4), `test_lead_state_carried_forward`.

## 6.21 Runtime budget (targets on the reference laptop, hero world)

| Stage group | Target |
|---|---|
| Ingest I01–I06 (1.5 M rows, CSV) | ≤ 3 min |
| E01–E08 (graph and on-chain) | ≤ 2 min |
| E09–E11 (network correlation, 2 passes) | ≤ 2 min |
| E12–E16 | ≤ 1.5 min |
| E17–E19 | ≤ 1 min |
| **Total, upload → published** | **≤ 10 min** |

These are targets, not claims. The benchmark job (§14.3) measures them on every release and the metrics page publishes the real numbers.

---


# PART 7 — THE MODELS

> Seven small, trained models plus one propagation algorithm. No GPU, no LLM. Every model beats a published rule baseline on worlds it has never seen, and every one ships with a model card. This part is the answer to R-PS-07: *"a working model — not just rules."*

## 7.1 The model catalogue

| Model | Level | Task | Labels from | Baseline it must beat | Headline metric | Target `[DEFAULT]` |
|---|---|---|---|---|---|---|
| `coinjoin_clf` | transaction | 6-class mixing structure | `truth/txs.is_coinjoin + kind`, batch payouts | Published rule set alone (Whirlpool, Wasabi, generic-equal-5) | macro-F1 (mixing classes); FP rate on batch payouts | F1 ≥ 0.95 · batch FP ≤ 1% |
| `change_clf` | output | Which output is change | `truth/addresses.is_change` | Classic heuristics (fresh address + script match + non-round) | precision at the merge threshold (p ≥ 0.95) | ≥ 0.99 |
| `peel_scorer` | chain | Laundering peel vs benign peel-like | `truth/txs.peel_chain_id` of illicit ops | Shape-only rule (≥ 5 hops, 2 outputs) | PR-AUC; recall on ≥ 5-hop chains | recall ≥ 0.9 |
| `origin_ranker` | (tx, candidate) + tx | Origin probability and observability | `truth/origins` | **first-spy** (vantage), **first-sender** (flow) | top-1 accuracy on observable txs; ECE | ≥ first-spy + 15 pts · ECE ≤ 0.05 |
| `er_pair_clf` | entity pair | Same owner? | `truth/addresses.agent_id` | CIOH alone | per-wallet recall gain at ≤ 2 pts precision loss | +10 pts recall |
| `anomaly_iforest` | tx + actor | Unsupervised outlier score | none (validated on injected outliers) | – | injected-outlier recall in the top 5% | ≥ 0.8 |
| `lead_ranker` | actor (+ CASHOUT calibrator) | Illicit actor probability | `truth/agents.illicit` | Taint-only ranking (sort by `taint_frac_in`) | **precision@50**, PR-AUC, ECE | P@50 ≥ 0.8 · PR-AUC ≥ 0.7 · ECE ≤ 0.05 |

The targets are **initial defaults** set before any data exists. They are revised once, after the first full evaluation in P3/P4, and then frozen. Moving a target after seeing the test set is cheating, and the decision log records any change.

## 7.2 Training data strategy

- **Worlds, not rows.** Models train on `train-rand` (40 domain-randomised worlds), are tuned on `val-rand` (10), and are reported on **`test-rand` (10, frozen seeds, never tuned on)** plus the stress packs. Splitting by world prevents the neighbour-memorisation leakage that inflates random-split results on Elliptic.
- **Train/serve parity.** Features are computed **by the engine itself**: the training pipeline runs the real stages E01…E(n−1) on each training world, then joins truth labels in `sutradhar_evals`. There is no separate feature code for training, so there is no skew between training and serving.
- **Class imbalance.** Illicit actors are 0.5–3% of actors. We use `scale_pos_weight` = negatives/positives (capped at 50) and early stopping on validation PR-AUC. We report PR-AUC and precision@k, never accuracy.
- **Determinism.** LightGBM `deterministic=True`, `force_row_wise=True`, `seed` fixed, `num_threads` fixed. Isolation Forest and randomized SVD use `random_state`. `test_training_is_deterministic` retrains `tiny` twice and compares model hashes.
- **Hyperparameters.** Sane defaults (`num_leaves 31`, `learning_rate 0.05`, `min_data_in_leaf 50`, `feature_fraction 0.8`, `bagging_fraction 0.8`, `lambda_l2 1.0`, ≤ 2,000 rounds with early stopping). An optional Optuna search on `val-rand` is `[STRETCH]`, and its result is written into the model card either way.

```bash
sutradhar train --model origin_ranker --train worlds/train --val worlds/val --out models/origin_ranker/1.3.0
sutradhar eval  --models models/ --worlds worlds/test --report reports/eval-1.3.0.json
```

## 7.3 Model specifications

Features are listed by name. Their definitions live in Part 6 (stage sections) and in code docstrings, which the model card quotes.

### 7.3.1 `coinjoin_clf`
Multi-class LightGBM (`objective = multiclass`, 6 classes). Features are in §6.5. The rule booleans are included as features, so the model *learns when the literature's heuristics fail* (for example Whirlpool-like shapes that are really payroll). Output: `p_coinjoin` and `kind_pred`.

### 7.3.2 `change_clf`
Binary LightGBM on outputs of candidate transactions (§6.7). The positive class is `truth.is_change`. The arg-max per transaction is decoded with a "no change" option when every output scores below 0.5.

### 7.3.3 `peel_scorer`
Binary LightGBM on chain-level features (§6.8), plus an isotonic calibrator. Negatives deliberately include **exchange hot-wallet payout sequences**, the classic peel-chain false positive.

### 7.3.4 `origin_ranker` (a bundle of two boosters)
- `pair_booster`: binary LightGBM on (transaction, candidate) pairs with the §6.11 features. The label is candidate == true origin (ip, session).
- `observable_booster`: binary LightGBM on transaction-level context features. The label is whether the true origin is in the candidate set.
- **Decoding:** per-transaction softmax of pair logits × P(observable). The top-1 probability is isotonic-calibrated.
- **Robustness:** it is trained on worlds that randomise sensors 5–80, taps, Tor and NAT, so it must generalise across observation models. The model card reports accuracy per observation model *and* per stress pack.

### 7.3.5 `er_pair_clf`
Binary LightGBM on blocked entity pairs (§6.14). The label is that both entities belong to the same true agent. It is trained with hard negatives: pairs that share a CGNAT IP, a Tor exit or an exchange counterparty but belong to different agents.

### 7.3.6 `anomaly_iforest`
Two scikit-learn `IsolationForest`s (transaction and actor level), each with 300 trees and `random_state` = seed. There are no labels. Validation injects synthetic outliers (extreme fee rates, dormancy-then-burst, unusual hours) into `tiny` and requires them to rank in the top 5%.

### 7.3.7 `lead_ranker` — the actor feature set (~70)

| Family | Features (examples; full list in `features.json` of the model artefact) |
|---|---|
| **TAINT** | `taint_frac_in`, `log_taint_sats_in`, `hops_to_seed`, `ppr_pct`, `n_seed_paths`, `best_path_strength`, `cashout_share_to_services`, `exposure_out` |
| **FLOW** | `n_entities`, `n_addresses`, `n_tx`, `coinjoin_in_share`, `coinjoin_out_share`, `postmix_consolidation` (CoinJoin outputs later co-spent), `peel_chains_operated`, `max_peel_hops`, `motif_scatter_gather`, `motif_cycle`, `motif_pass_through`, `fan_in_z`, `fan_out_z`, `mean_dwell_h`, `value_in_log`, `value_out_log`, `round_amount_pref` |
| **NET** | `n_sessions`, `n_ips`, `max_control_p`, `mean_origin_p_top`, `share_unobservable`, `tor_share`, `vpn_share`, `hosting_share`, `n_countries`, `n_asns`, `main_ip_crowdedness`, `co_origin_degree`, `listener_share` |
| **ANOM** | `tx_anomaly_max_pct`, `tx_anomaly_mean_pct`, `actor_anomaly_pct` |
| **BEHAV** | `tz_confidence`, `hour_entropy`, `burstiness_cv`, `dormancy_burst`, `fee_rate_median`, `fee_rate_cv`, `rbf_share`, `address_reuse_rate`, `script_mix_entropy` |
| **Elliptic++-comparable** | `txs_as_sender`, `txs_as_receiver`, `btc_sent_total`, `btc_received_total`, `fees_total`, `fees_share`, `blocks_between_txs_mean` (time ÷ 600 s), `lifetime_blocks`, `addr_interactions_total`, `repeat_interactions` (definitions mirror Elliptic++ Table 3, so §7.8 is possible) |

The **CASHOUT calibrator** is an isotonic map from a small logistic score over (`taint_frac`, `log_taint_sats`, `hops_to_seed`, `service_score`) to "this deposit belongs to an illicit customer", fitted on `val-rand`.

## 7.4 Calibration — what "confidence" means, stated honestly

Every probability shown to a user has been **isotonic-calibrated on held-out validation worlds**. The model card shows a reliability diagram and the **Expected Calibration Error**. The sentence we are entitled to say is:

> *"On worlds the model never saw, among leads it scored around 0.8, about 80% were truly illicit."*

The sentence we are **not** entitled to say is that it holds on NTRO's real traffic. Calibration transfers only as far as the data distribution does. So the platform:
1. flags leads scored under **drift** (§7.6);
2. **re-fits calibration from analyst feedback** once ≥ 200 labelled leads exist (§7.7), and the model card records which calibration is active;
3. prints the calibration basis in the evidence pack ("calibrated on: synthetic validation worlds val-rand@v3").

## 7.5 Registry, model cards and the promotion gate

```
models/<name>/<version>/
├── model.txt            LightGBM text dump(s) (bundle = several files) · or iforest.joblib
├── calibration.json     isotonic breakpoints
├── features.json        ordered feature names, types, family, description
├── reference_hist.json  per-feature training histograms (10 quantile bins) for drift
├── metrics.json         val + test-rand + stress-pack metrics, baselines, CIs (bootstrap over worlds)
├── card.md              model card (below)
└── SHA256SUMS
```

**The model card** (rendered in Govern and on the docs site) has these sections:
- intended use and **out-of-scope uses**;
- training worlds and their parameter ranges;
- features and families;
- metrics against baselines with 95% CIs;
- metrics per observation model and per stress pack;
- the calibration plot;
- known failure modes, taken from the red-team report;
- ethical considerations;
- version history.

**States:** `candidate → shadow → active → retired`. Exactly one `active` per model name, enforced by a unique partial index.

**Promotion gate** (I14): a version becomes `active` only if its `metrics.json` meets the model's targets (§7.1) **and** does not regress the active version by more than 1 point on the headline metric on `test-rand`. Promotion is admin-only, audited, and reversible in one click (roll back to the previous active version).

## 7.6 Drift

For every run, E17 computes each feature's **Population Stability Index** against the model's `reference_hist.json`:

| PSI | Severity | What happens |
|---|---|---|
| < 0.10 | none | – |
| 0.10 – 0.25 | moderate | Govern → Drift shows it; the model card link warns |
| > 0.25 | **major** | Every lead from that run carries a "scored under drift" banner, and the run summary names the drifting features |

That is the honest behaviour when NTRO's data looks different from our worlds. It is also a good finale answer: *"here is how the system tells you it's out of its depth."*

## 7.7 The feedback loop — the ranker learns from the analyst

1. Analysts confirm or dismiss leads with reason codes (§2.5.3). Each verdict is a `feedback` row tied to `lead_key` and run.
2. **Label mapping:**
   - `confirm` → positive;
   - `dismiss` with `victim`, `benign_service` or `known_false_positive_pattern` → negative;
   - `insufficient_evidence` and `duplicate` → excluded;
   - `escalate` → no label yet.
3. **Retrain job** (`kind = retrain`, admin-triggered or nightly when ≥ 50 new labels exist `[DEFAULT]`). The training set is the synthetic `train-rand` features plus analyst-labelled actor feature vectors from real runs (weight 5 `[DEFAULT]`). The output is a new `lead_ranker` **candidate**.
4. **Shadow evaluation.** The candidate re-scores the latest run *alongside* the active model. It is compared on (a) `test-rand` and (b) a **held-out 30% of analyst labels**. Govern shows *precision@20 before vs after*.
5. **Promotion** follows the §7.5 gate. The calibration is re-fitted on analyst labels once ≥ 200 exist.

This is the "human-in-the-loop" judges ask about. We demo it live: dismiss three false positives with reasons, click retrain, and watch precision@20 on the held-out labels move.

## 7.8 External validity on real data — Elliptic++ `[STRETCH]`

Elliptic++ (Elmougy & Liu, KDD 2023) has **822 k real, labelled Bitcoin wallet addresses with named features**: BTC sent/received, fees, blocks between transactions, lifetime, interaction counts (its Table 3). Our `lead_ranker` feature set includes Elliptic++-comparable definitions (§7.3.7). So we:

1. train a wallet-level LightGBM on Elliptic++ using **only** the features we can compute identically, with a temporal split as in the paper;
2. report its PR-AUC in the write-up as *"our feature definitions carry signal on real labelled Bitcoin data"*;
3. do **not** feed it into production scoring. The domain mismatch (2019-era data, different labelling rules) would make its scores uncalibrated for our worlds.

Data: the Google Drive folder linked from the `git-disl/EllipticPlusPlus` README (§17.14). It is downloaded once, on a connected machine. It is never needed at runtime.

## 7.9 What we deliberately do not do

| Not doing | Because |
|---|---|
| A GNN as the core model | On Elliptic, Random Forest (illicit F1 0.788) beat GCN (0.628) and EvolveGCN (0.720) (Weber et al. 2019). An independent Elliptic++ reproduction found XGBoost PR-AUC 0.669 vs GraphSAGE 0.448. Graph structure already enters our trees through engineered graph features. We run a GraphSAGE **experiment** `[STRETCH]` and report it honestly in the write-up. |
| An LLM anywhere in scoring or narrative | Offline requirement; hallucination liability in forensic output; nothing it would add that templates do not. |
| Deep sequence models for peel chains | Chain-level engineered features plus boosting are accurate, explainable and CPU-cheap. |
| AutoML | Unexplainable choices; slow; unnecessary at our scale. |

---


# PART 8 — EXPLAINABILITY, EVIDENCE & INTEROPERABILITY

## 8.1 Anatomy of an explanation

Every lead opens to the same tabs. This is what R-PS-08 and R-PS-20 look like in practice:

| Tab | Contents | Source |
|---|---|---|
| **Summary** | One hedged sentence, grade, calibrated p, priority, families, value at risk, last activity | `lead` |
| **Why** | Top 6 supporting and top 2 opposing reasons, each with its feature value and contribution (log-odds). Grouped by family. | `lead_contrib` → templates |
| **Evidence graph** | The explanation subgraph (≤ 150 nodes), styled by method and confidence, clickable into the canvas | `lead_subgraph` |
| **Network** | Origin attribution per transaction: candidates, p, p(unobservable), sessions, IP enrichment with source and as-of date, **Replay** button | `origin`, `control`, `ip_enrich` |
| **Path to seed** | The k-best taint paths, hop by hop, with transaction references and fractions | `risk_path` |
| **What would clear this** | The counterfactual steps (§8.3) | `lead_cf` |
| **Timeline** | Every transaction of the subject in time, with the hour-of-day histogram and inferred offset | `tz_profile`, `tx` |
| **Provenance** | Run manifest link, model versions and hashes, refdata versions, drift flags, "calibrated on …" | `run_meta`, `drift` |
| **Priority** | The priority decomposed into its four factors (§2.5.3) | `lead` |

## 8.2 Reason templates

Feature contributions become sentences through a template catalogue (`packages/engine/sutradhar_engine/explain/templates.yaml`). **Every template is hedged** (I17). Examples:

| Feature(s) | Template | Rendered example |
|---|---|---|
| `taint_frac_in`, `hops_to_seed`, category | "About {pct}% of the value this actor received **traces to** watchlisted {category} wallets within {hops} hops." | "About 41% of the value this actor received traces to watchlisted ransomware wallets within 3 hops." |
| `peel_chains_operated`, `max_peel_hops`, CV | "Operates a {n}-hop peel chain with **regular** {interval} spacing, **consistent with** automated laundering." | "…a 23-hop peel chain with regular ~12-minute spacing…" |
| `postmix_consolidation` | "Mixed outputs were **later spent together**, which re-links them to one owner." | – |
| `cashout_share_to_services` | "{pct}% of outflow reached deposit addresses at {n} services ({names})." | "…at 3 services (EXB, EXD, EXE)." |
| `max_control_p`, IP | "Transactions **were most likely broadcast** from {ip} ({as_org}, {country}), p = {p}." | "…from 49.36.x.x (Reliance Jio, IN), p = 0.82." |
| `co_origin_degree` | "Shares broadcast sessions with {n} otherwise unlinked wallet cluster(s)." | – |
| `tor_share` | "{pct}% of broadcasts came via Tor exits; origin for these is **not observable**." | – |
| `tz_confidence`, offset | "Activity pattern **is consistent with** a UTC{offset} daily schedule (confidence {c})." | "…UTC+05:30 daily schedule (confidence 0.74)." |
| `dormancy_burst` | "Dormant for {d} days, then {n} transactions within {h} hours." | – |
| `tx_anomaly_max_pct` | "Includes a transaction more unusual than {pct}% of all transactions in this dataset." | – |
| opposing: `service_score` | "Argues against: behaves partly like a service (many counterparties, 24-hour activity)." | – |
| opposing: `share_unobservable` | "Argues against: most broadcasts were not observable, so network evidence is thin." | – |

## 8.3 Counterfactual — "what would clear this"

```python
def counterfactual(x, booster, calib, ref_benign_median, threshold, max_steps=5):
    """Greedy: neutralise the strongest supporting features until p < threshold."""
    steps, x_cf = [], x.copy()
    contrib = booster.predict(x[None, :], pred_contrib=True)[0][:-1]  # last column = bias
    for j in np.argsort(-contrib):  # strongest supporting first
        if contrib[j] <= 0 or len(steps) == max_steps:
            break
        before = x_cf[j]
        x_cf[j] = ref_benign_median[j]
        p = calib(booster.predict(x_cf[None, :], raw_score=True)[0])
        steps.append((FEATURES[j], before, x_cf[j], p))
        if p < threshold:
            break
    return steps
```

It renders as: *"If the traceable share from watchlisted wallets were ≤ 2% (it is 41%) **and** there were no 23-hop peel chain, this would score 0.31, below grade C."* Analysts use this to judge whether a lead is resting on one fragile fact or on several.

## 8.4 The evidence subgraph

For each lead, E18 assembles a bounded subgraph in priority order until it reaches **150 nodes** `[DEFAULT]`:
1. the subject;
2. the k-best seed paths (all hops);
3. peel-chain hops;
4. CASHOUT addresses and their services;
5. top-10 `ORIGINATED` edges with IPs and sessions;
6. `CONTROLS` and `CO_ORIGIN` edges;
7. sampled member addresses (≤ 20, with the total count shown on the entity node).

Every edge carries its envelope (method, confidence, evidence refs, model version). The canvas encodes those visually (§10.6).

## 8.5 The language guard

`test_reason_templates_are_hedged` lints every template and every generated summary:
- **Forbidden phrases:** "is the owner", "belongs to" (without *likely*), "criminal", "guilty", "confirmed" (outside status labels), "identity of", "definitely", "proves".
- **Required:** each template contains one of *likely · consistent with · traces to · most likely · suggests · argues against*, or is a pure measurement ("sent 12 transactions").

This is small and cheap, and it is exactly what an NTRO evaluator, who knows the difference between a lead and evidence, will notice.

## 8.6 The audit hash chain

```python
# apps/api/sutradhar_api/audit.py
GENESIS = "0" * 64

def append(session, *, actor, role, action, target_kind, target_ref, payload) -> AuditEntry:
    head = session.execute(select(AuditHead).where(AuditHead.id == 1).with_for_update()).scalar_one()
    seq = head.seq + 1
    body = canonical_json({
        "seq": seq, "ts": utcnow_iso(), "actor": actor, "role": role, "action": action,
        "target": [target_kind, target_ref], "payload": payload, "prev": head.entry_hash,
    })
    entry_hash = sha256_hex(body)
    session.add(AuditLog(seq=seq, ts=..., actor_id=actor, actor_role=role, action=action,
                         target_kind=target_kind, target_ref=target_ref, payload=payload,
                         prev_hash=head.entry_hash, entry_hash=entry_hash))
    head.seq, head.entry_hash = seq, entry_hash          # same transaction as the mutation (I13)
    return ...

def verify(session) -> VerifyResult:
    prev = GENESIS
    for row in session.execute(select(AuditLog).order_by(AuditLog.seq)).scalars():
        body = canonical_json({...row fields..., "prev": prev})
        if row.prev_hash != prev or sha256_hex(body) != row.entry_hash:
            return VerifyResult(ok=False, broken_at=row.seq)
        prev = row.entry_hash
    return VerifyResult(ok=True, head=prev)
```

**Audited actions** (non-exhaustive):
- `auth.login`, `auth.failed`;
- `dataset.upload`, `dataset.map`, `run.start`, `run.published`;
- `lead.status`, `lead.assign`, `lead.feedback`, `merge.accept`, `merge.reject`;
- `case.create`, `case.item_add`, `case.note`, `case.close`;
- `export.create`, `export.approve`, `export.download`, `verify.run`;
- `watchlist.add`, `watchlist.remove`;
- `model.promote`, `model.rollback`;
- `settings.change`, `user.create`, `user.role_change`, `refdata.update`, `demo.reset`.

Read access to sensitive views (dossier opens, evidence graph opens) is logged to a separate high-volume access log. It is not chained, and it is rotated.

## 8.7 The evidence pack

```
case_01JC…_evidence_2026-11-21T1432+0530.zip
├── README.txt                    how to verify, in plain language
├── case.json                     case metadata, items, notes, statuses, owner, timestamps
├── leads/
│   └── <lead_key>.json           lead + reasons + contributions + counterfactual + subgraph (with envelopes)
├── report.pdf                    human-readable report (WeasyPrint), every claim footnoted to evidence refs
├── graph.graphml                 the case's combined evidence graph (opens in Gephi / yEd / i2 via import)
├── source_rows.csv               exact source records cited (file_id, row_no, raw fields) — CSV-neutralised
├── run_manifest.json             dataset digests, code/image version, model versions + hashes, refdata, settings hash
├── audit_excerpt.jsonl           audit entries touching this case + the chain head at export time
├── hash_report.txt               SHA-256 of every file above, algorithm stated, generation time (IST + UTC)
└── SHA256SUMS                    machine-checkable (sha256sum -c SHA256SUMS)
```

**Verification** (`POST /api/v1/verify`, or `sutradhar verify pack.zip` fully offline, with no server):
1. `SHA256SUMS` matches every file.
2. `hash_report.txt` agrees with `SHA256SUMS`.
3. Every lead's evidence refs resolve inside the pack (`source_rows.csv`, `graph.graphml`).
4. `audit_excerpt.jsonl` is internally chain-consistent, and its head is *ancestor-consistent* with the live chain (when verified on the originating system).
5. **Optional re-run.** If the original dataset is available, re-run with the manifest and assert the same `result_digest`. This is **full reproducibility**, not just integrity.

The result is a JSON report plus a green or red seal in the UI. Verifications are themselves audited.

## 8.8 Alignment with Indian electronic-evidence law (BSA 2023, s.63)

Under the Bharatiya Sakshya Adhiniyam, 2023 (in force since 1 July 2024), **Section 63** governs the admissibility of electronic records. Section 63(4) requires a certificate accompanying the record, and the prescribed certificate format in the Schedule asks for **the hash value(s) of the electronic record and the algorithm used (SHA1 / SHA256 / MD5 / other), with a hash report enclosed**.

| What the certificate needs | What the pack provides |
|---|---|
| Identification of the electronic record and how it was produced | `run_manifest.json` (exact code, model and data versions) plus `report.pdf` §Method |
| Particulars of the device/system involved | `run_manifest.code` (image digest, version) plus the system description in the README |
| Hash value(s) and algorithm | `hash_report.txt` (SHA-256 for every file) |
| Hash report enclosed | `hash_report.txt` is exactly that |
| Signature of the person in charge / an expert | **Human.** The platform never signs on anyone's behalf. It produces the material a responsible officer certifies. |

We state this carefully in the write-up. **This is engineering alignment, not legal advice.** The pack is built so that the officer who certifies it has every fact the certificate asks for, computed by a process they can re-run.

## 8.9 Interoperability exports

| Export | Format | Use | Notes |
|---|---|---|---|
| **MISP event** | MISP JSON | Share indicators with CERT/threat-intel platforms | Addresses as `btc` attributes; `btc-wallet`, `btc-transaction`, `coin-address` objects; IPs as `ip-src`; tags for grade and families; `to_ids = false` by default (these are leads) |
| **STIX 2.1 bundle** | JSON | Standard CTI exchange | Converted from the MISP event with `misp-stix` (offline library) |
| **GraphML / GEXF** | XML | Gephi, yEd, NetworkX | Edge attributes carry the envelope |
| **i2-importable CSV** | `entities.csv` + `links.csv` | IBM i2 Analyst's Notebook import specifications | Stable IDs, typed entities, link labels = edge method, confidence as an attribute |
| **PDF report** | PDF | Human dissemination | WeasyPrint, IST timestamps with offset, footnoted evidence |
| **CSV / XLSX tables** | CSV | Spreadsheet work | Formula-injection neutralised (I16): cells starting `= + − @ \t \r` are prefixed with `'` |

---


# PART 9 — THE API SURFACE

## 9.1 Shape and conventions

| Concern | Convention |
|---|---|
| Base path | `/api/v1` · JSON · UTF-8 · `snake_case` |
| Time | ISO-8601 in UTC (`…Z`) in responses, plus `*_us` integers where microsecond precision matters (relay timing). The UI converts to IST with a visible offset. |
| Money | Integer satoshis in every field named `*_sats`. The UI formats BTC. |
| Auth | `POST /auth/login` → `{access_token (JWT, 20 min), refresh_token (opaque, 12 h), user}`. `Authorization: Bearer <access>`. **Refresh rotation:** each refresh returns a new pair and revokes the old one. Reuse of a revoked refresh token revokes the whole session family. Demo: `POST /auth/demo` (rate-limited per IP). |
| Authorisation | One dependency, `require("<action>")`, on every route (§2.4). `test_every_mutating_endpoint_declares_permission`. |
| Errors | **RFC 9457** `application/problem+json`: `{type, title, status, detail, instance, errors[]}`. `type` is a URN (`urn:sutradhar:problem:validation`), never a URL, so nothing tempts a client to fetch it. |
| Pagination | Cursor-based: `?limit=50&cursor=…` → `{items, next_cursor}`. `limit ≤ 500` everywhere (I12). |
| Idempotency | `Idempotency-Key` header on job-creating POSTs (datasets, runs, exports, lab jobs). The same key returns the same job. |
| Long work | Always a **job**. The POST returns `202 {job_id, …}`. Progress arrives over SSE. |
| Realtime | `GET /api/v1/events?topics=job:<id>,run:<id>,leads` (Server-Sent Events). The client uses `@microsoft/fetch-event-source`, so the **token travels in a header, never in a URL**. 15 s heartbeats. Resume with `Last-Event-ID` (= `job_events.id`). |
| Rate limits | Per user and per IP, stricter in demo mode (§12.7) |
| API docs | OpenAPI at `/api/openapi.json`, Swagger UI at `/api/docs` **with self-hosted static assets**. FastAPI's default Swagger page loads its JS/CSS from a CDN, which would break I11 offline, so we serve local copies via `get_swagger_ui_html(swagger_js_url=…, swagger_css_url=…)`. |

## 9.2 Resource map

| Method · Path | Role | Purpose | Phase |
|---|---|---|---|
| **Auth & system** | | | |
| `POST /auth/login` · `/auth/refresh` · `/auth/logout` | any | Session lifecycle | P0 |
| `POST /auth/demo` | public (demo only) | One-click demo session | P0 |
| `GET /me` | any | Current user, role, permissions | P0 |
| `GET /health` · `GET /ready` | public | Liveness / readiness (DB, data volume, models loaded) | P0 |
| `GET /system/info` | any | Mode, version, git SHA, **offline-guard status**, refdata as-of dates | P0 |
| **Datasets & ingestion** | | | |
| `POST /datasets` | analyst+ | Multipart upload (or server-side path in `/data/inbox` in airgap) → 202 job (I01–I06) | P2 |
| `GET /datasets` · `GET /datasets/{id}` | any | List / detail with status | P2 |
| `GET /datasets/{id}/xray` | any | Capability profile and X-ray | P2 |
| `GET /datasets/{id}/rejects?rule=&cursor=` | any | Row-level rejects (and `?format=csv`, neutralised) | P2 |
| `POST /datasets/{id}/mapping` | analyst+ | Apply a profile or inline spec → re-run I02–I06 | P2 |
| `GET/POST /mapping-profiles` · `GET /mapping-profiles/{id}` | analyst+ | Saved, versioned profiles | P2 |
| **Runs & jobs** | | | |
| `POST /runs` | analyst+ | `{dataset_id, overrides?}` → 202 job (E01–E19) | P3 |
| `GET /runs` · `GET /runs/{id}` | any | List / detail, stage progress | P3 |
| `GET /runs/{id}/manifest` | any | The run manifest (§4.10) | P5 |
| `GET /runs/{id}/diff?against=` | any | New / changed / gone leads | P5 |
| `POST /runs/{id}/reverify` | lead+ | Re-run from the manifest and compare `result_digest` → job | P8 |
| `GET /jobs/{id}` · `POST /jobs/{id}/cancel` | owner / admin | Job status / cancel | P0 |
| `GET /events` | any | SSE stream | P0 |
| **Leads & triage** | | | |
| `GET /runs/{id}/leads?type=&grade=&status=&family=&min_p=&q=&sort=&cursor=` | any | The queue | P5 |
| `GET /leads/{lead_id}` | any | Summary plus workflow state | P5 |
| `GET /leads/{lead_id}/explanation` | any | Why, opposing reasons, counterfactual, priority decomposition, provenance | P5 |
| `GET /leads/{lead_id}/subgraph` | any | Evidence subgraph with envelopes | P5 |
| `PATCH /leads/by-key/{lead_key}/state` | analyst+ | Status, assignee (lead+), snooze | P5 |
| `POST /leads/by-key/{lead_key}/feedback` | analyst+ | Verdict and reason code (dismiss requires a reason) | P5 |
| **Objects (run-scoped)** | | | |
| `GET /runs/{id}/actors/{ref}` | any | Actor dossier | P6 |
| `GET /runs/{id}/entities/{ref}` · `/addresses/{addr}` · `/tx/{txid}` · `/ips/{ip}` · `/sessions/{ref}` | any | Object pages | P6 |
| `GET /runs/{id}/actors/{ref}/merge-suggestions` | any | ER suggestions for this actor | P4 |
| `POST /merge-decisions` | lead | Accept / reject a suggestion → analyst assertion | P4 |
| **Graph, replay, geo, flows, search** | | | |
| `GET /runs/{id}/graph/neighbors?node=&edge_types=&min_conf=&limit=` | any | Neighbourhood expansion for the canvas | P6 |
| `POST /runs/{id}/graph/paths` | any | `{from, to, k, max_hops, edge_types}` → k-best paths | P6 |
| `GET /runs/{id}/graph/overview?level=actor&top=` | any | Top-N actor graph for the Sigma overview | P6 |
| `GET /runs/{id}/tx/{txid}/propagation` | any | Replay payload (§9.3.5) | P7 |
| `GET /runs/{id}/geo/flows?level=country\|asn&min_sats=` | any | Flow arcs and origin points | P6 |
| `GET /runs/{id}/flows/sankey?root=&depth=` | any | Follow-the-money Sankey | P6 |
| `GET /runs/{id}/search?q=` | any | Omnibox: auto-detects txid / address / IP / ASN / actor | P6 |
| **Watchlists** | | | |
| `GET/POST /watchlists` · `GET/POST/DELETE /watchlists/{id}/items` · `POST /watchlists/{id}/import` | lead+ | Seed management (CSV import) | P5 |
| **Cases & evidence** | | | |
| `GET/POST /cases` · `GET/PATCH /cases/{id}` | analyst+ | Cases | P6 |
| `POST /cases/{id}/items` · `DELETE /cases/{id}/items/{item_id}` | analyst+ | Add or remove items (removal is audited; the audit keeps the item) | P6 |
| `POST /cases/{id}/notes` | analyst+ | Markdown notes | P6 |
| `POST /cases/{id}/exports` | analyst+ | `{kind: evidence_pack\|misp\|stix\|graphml\|i2csv\|pdf}` → 202 job | P6/P7 |
| `POST /exports/{id}/approve` | lead | Required for escalated cases | P6 |
| `GET /exports/{id}` · `GET /exports/{id}/download` | owner / lead+ | Status / download (audited) | P6 |
| `POST /verify` | any | Multipart pack → job → verification report | P6 |
| **Lab** | | | |
| `GET /lab/scenarios/presets` · `POST /lab/scenarios` · `GET /lab/scenarios[/{id}]` | lead+ (demo: presets only) | Generate a world → dataset | P7 |
| `POST /lab/evaluations` · `GET /lab/evaluations[/{id}/report]` | lead+ | `{kind: eval\|redteam\|planner, spec}` → job → report | P7 |
| `GET /lab/academy/challenges[/{id}]` · `POST …/{id}/attempts` · `GET /lab/academy/leaderboard` | any | Academy | P7 |
| **Govern** | | | |
| `GET /models` · `GET /models/{name}/{version}` | any | Registry, card, metrics | P7 |
| `POST /models/{name}/{version}/promote` · `POST /models/{name}/rollback` | admin | Gated promotion (I14) / rollback | P7 |
| `POST /models/lead_ranker/retrain` | admin | Feedback retrain → candidate plus shadow report | P7 |
| `GET /runs/{id}/drift` | any | PSI per feature per model | P7 |
| `GET/POST/PATCH /users` | admin | User management | P6 |
| `GET /settings` · `PUT /settings/{key}` | admin (read: any) | Settings, with defaults and "changed from default" markers | P6 |
| `GET /audit?cursor=` · `GET /audit/verify` | lead+, auditor | Audit log / chain verification | P6 |
| `GET /refdata` · `POST /refdata/import` | admin | Reference-data sources · import a signed snapshot bundle (airgap) | P8 |
| `POST /demo/reset` | admin (demo) | Reset the demo world now | P8 |

## 9.3 The endpoints that carry the most weight

### 9.3.1 `POST /api/v1/datasets`
```http
POST /api/v1/datasets
Idempotency-Key: 5c1f…
Content-Type: multipart/form-data; boundary=…
  name=ntro-sample-2026-12-10
  profile_id=mp_01JB…            (optional; else auto-map)
  files[]=@traffic_part1.csv.gz
  files[]=@traffic_part2.csv.gz
```
```json
202 Accepted
{ "dataset": {"id": "ds_01JC2…", "status": "uploaded"},
  "job": {"id": "job_01JC2…", "kind": "ingest", "status": "queued"} }
```

### 9.3.2 `GET /api/v1/runs/{id}/leads`
```json
{ "items": [
    { "id": "ld_01JC…", "lead_key": "a41c09e2b7f3d615", "type": "ACTOR",
      "title": "Actor A-0117 · ransomware-linked operator",
      "summary": "Likely one operator controlling 4 wallet clusters; about 41% of inflow traces to watchlisted ransomware wallets.",
      "p": 0.93, "grade": "A", "families": ["NET","FLOW","TAINT","BEHAV"],
      "priority": 2.71, "value_at_risk_sats": 1402200000, "last_activity_at": "2026-08-21T19:44:02Z",
      "state": {"status": "NEW", "assignee": null, "changed_since_review": false} } ],
  "next_cursor": "eyJwIjoyLjcxLCJpZCI6Imxk…" }
```

### 9.3.3 `GET /api/v1/leads/{id}/explanation`
```json
{ "reasons": [
    {"family": "TAINT", "feature": "taint_frac_in", "value": 0.41, "contribution": 1.92,
     "text": "About 41% of the value this actor received traces to watchlisted ransomware wallets within 3 hops."},
    {"family": "FLOW", "feature": "max_peel_hops", "value": 23, "contribution": 1.10,
     "text": "Operates a 23-hop peel chain with regular ~12-minute spacing, consistent with automated laundering."}],
  "opposing": [
    {"family": "NET", "feature": "share_unobservable", "value": 0.31, "contribution": -0.22,
     "text": "Argues against: 31% of broadcasts were not observable (Tor), so network evidence is partial."}],
  "counterfactual": [
    {"feature": "taint_frac_in", "from": 0.41, "to": 0.02, "p_after": 0.62},
    {"feature": "max_peel_hops", "from": 23, "to": 0, "p_after": 0.31}],
  "priority": {"p": 0.93, "value_factor": 2.15, "recency_factor": 0.97, "actionable_factor": 1.25},
  "provenance": {"run_id": "run_01JC…", "result_digest": "5d0f…",
                 "models": {"lead_ranker": "1.4.0"}, "calibrated_on": "val-rand@v3",
                 "drift": "none"} }
```

### 9.3.4 `GET /api/v1/runs/{id}/graph/neighbors`
```
?node=actor:A-0117&edge_types=CONTROLS,ORIGINATED,TAINT_PATH&min_conf=0.5&limit=200
```
```json
{ "nodes": [{"id":"ip:49.36.x.x","type":"IP","label":"49.36.x.x","attrs":{"asn":55836,"country":"IN","is_tor_exit":false}}],
  "edges": [{"id":"e1","type":"CONTROLS","source":"ip:49.36.x.x","target":"entity:E-88121",
             "method":"control_agg","confidence":0.82,"model_version":"origin_ranker@1.3.0",
             "evidence_refs":{"txids":["9c1e…","d07a…"]}}],
  "truncated": false }
```

### 9.3.5 `GET /api/v1/runs/{id}/tx/{txid}/propagation` (the Replay payload)
```json
{ "txid": "9c1e…", "t0_us": 1787341442113204,
  "nodes": [{"id":"ip:49.36.x.x:51544","kind":"candidate","x":0.12,"y":0.44},
            {"id":"sensor:S12","kind":"sensor","x":0.55,"y":0.31}],
  "events": [{"t_us": 812345, "from": "ip:49.36.x.x:51544", "to": "sensor:S12", "rank_at_sensor": 1}],
  "posterior": [
    {"t_us": 500000,  "candidates": [{"id":"ip:49.36.x.x:51544","p":0.38},{"id":"ip:185.220.x.x","p":0.21}], "p_unobservable": 0.33},
    {"t_us": 3000000, "candidates": [{"id":"ip:49.36.x.x:51544","p":0.81}], "p_unobservable": 0.07}],
  "ledger": {"inputs": [["bc1q…", 42000000]], "outputs": [["bc1q…", 3100000],["bc1q…", 38850000]]} }
```
The posterior checkpoints are computed by **actually re-running `origin_ranker` on the observations available up to each time *t***. They are not animated for effect. The convergence the audience watches is the model's real behaviour.

### 9.3.6 `POST /api/v1/cases/{id}/exports` → evidence pack
```json
{ "kind": "evidence_pack", "include": {"source_rows": true, "graphml": true, "pdf": true} }
→ 202 { "export": {"id": "exp_01JC…", "status": "queued"}, "job": {"id": "job_01JC…"} }
```

### 9.3.7 `POST /api/v1/verify`
Returns `202 {job}`. The report:
```json
{ "ok": true, "files_checked": 9, "sha256_mismatches": [], "refs_unresolved": 0,
  "audit_excerpt": {"chain_ok": true, "ancestor_of_live_head": true},
  "reproducibility": {"attempted": true, "result_digest_match": true} }
```

## 9.4 SSE event catalogue

| Event | Payload | Emitted by |
|---|---|---|
| `job.progress` | `{job_id, stage, pct, message}` | Worker (every stage transition and each ~2% within long stages) |
| `job.completed` / `job.failed` | `{job_id, result \| error}` | Worker |
| `dataset.status` | `{dataset_id, status, xray_ready}` | Ingest job |
| `run.stage` | `{run_id, stage, ms}` | Engine |
| `run.published` | `{run_id, new, changed, gone}` | E19 |
| `lead.watchlist_hit` | `{run_id, lead_key, value, watchlist}` | E19 (rule-labelled) |
| `demo.reset_soon` | `{at}` | Demo scheduler (10-minute warning banner) |

## 9.5 One contract, two languages

- `apps/api` exports its OpenAPI schema (`sutradhar api openapi > packages/ts-client/openapi.json`).
- `openapi-typescript` generates types, and `openapi-fetch` gives a typed client (`packages/ts-client`).
- CI regenerates and fails on diff (`git diff --exit-code packages/ts-client`). A backend change that breaks the frontend therefore fails at build time, not in a demo.

---


# PART 10 — FRONTEND ARCHITECTURE & THE DESIGN SYSTEM

## 10.1 Stack, with the reason for each choice

| Concern | Choice | Why |
|---|---|---|
| App | React 19 + Vite + TypeScript (strict) | The static build runs on Vercel and offline behind Caddy with no Node server |
| Routing | TanStack Router (file routes, typed search params) | Filters, the selected run and panel state live **in the URL**, so a link is shareable and reproducible |
| Server state | TanStack Query v5 | Key-based invalidation when SSE events land (`run.published` → invalidate `['leads', runId]`) |
| Tables | TanStack Table + TanStack Virtual | 100k-row virtualised queue and reject tables |
| Forms | react-hook-form + zod | Mapping wizard, scenario forms, settings |
| UI kit | Tailwind v4 + shadcn/ui (Radix), copied into the repo | We own every component. Accessible primitives. |
| Canvas | Cytoscape.js + `cytoscape-fcose` | Compound nodes (entity ⊂ actor), rich styling by edge data, ≤ ~2k nodes interactive |
| Big graphs | Sigma.js + graphology (+ ForceAtlas2 in a Web Worker) | WebGL overview up to ~50k nodes |
| Maps | deck.gl (`GeoJsonLayer`, `ArcLayer`, `ScatterplotLayer`) + Natural Earth 1:110m countries GeoJSON (bundled) | Flow arcs with **no tile server** |
| Charts | Apache ECharts | Sankey, histograms, calibration curves, robustness curves |
| SSE | `@microsoft/fetch-event-source` | Authorization header on SSE; reconnect with `Last-Event-ID` |
| Omnibox | cmdk | ⌘K |
| i18n | i18next + react-i18next | English / हिंदी UI chrome |
| Dates | date-fns + date-fns-tz | IST display with explicit offsets |
| Fonts | IBM Plex Sans + IBM Plex Mono via Fontsource (self-hosted, OFL) | Offline (I11). Mono for every identifier. |

## 10.2 Project structure

```
apps/web/src/
├── app/                    router, providers (Query, i18n, theme, auth), shell layout, error boundary
├── routes/                 file-based routes (TanStack Router plugin)
├── features/
│   ├── auth/  system/  overview/
│   ├── ingest/             dropzone, mapping wizard, progress stepper, x-ray, rejects
│   ├── triage/             queue, filters, saved views, hotkeys, preview panel
│   ├── leads/              lead detail + the 9 tabs (§8.1)
│   ├── investigate/        cytoscape canvas, path finder, inspector, sigma overview
│   ├── replay/             wire ⇄ ledger replay
│   ├── dossiers/           actor, entity, address, tx, ip, session
│   ├── geo/  flows/        deck.gl map · ECharts sankey
│   ├── cases/  evidence/   case workspace · exports · verify
│   ├── lab/  academy/      scenario studio · evaluations · red-team · planner · academy
│   └── govern/             models, drift, users, settings, audit, refdata, system
├── components/
│   ├── ui/                 shadcn copies (button, dialog, tabs, table, sheet, command, …)
│   ├── evidence/           GradeBadge · FamilyChips · ConfidenceBar · ProvenanceTag · EnvelopePopover · HashChip
│   ├── graph/              cytoscape styles, legend, controls
│   └── data/               DataTable (virtualised), EmptyState, ErrorState, Skeletons
├── lib/                    api (ts-client), sse, format (sats/BTC, IST), hotkeys, i18n, snapshot, featureFlags
├── styles/                 tokens.css (from @sutradhar/tokens), globals.css
└── assets/                 fonts/, geo/ne_110m_admin_0_countries.json, icons/
```

## 10.3 Information architecture

```
┌ Top bar ─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ◆ Sutradhar   [Run: run_01JC… ▾  hero-ghostline · published 14:32 IST]   ⌘K Search…   AIR-GAPPED ✓   A│
├──────────┬───────────────────────────────────────────────────────────────────────────────────────────┤
│ Overview │                                                                                           │
│ Ingest   │                                    (page)                                                 │
│ Triage ● │                                                                                           │
│ Investig.│                                                                                           │
│ Cases    │                                                                                           │
│ Lab      │                                                                                           │
│ Govern   │                                                                                           │
├──────────┴───────────────────────────────────────────────────────────────────────────────────────────┤
│ Status: job_01JC… E10 origin 62% ████████░░░  ·  drift: none  ·  refdata 2026-09  ·  v1.0.0 (4e1b9c2) │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Mode badge:** `AIR-GAPPED ✓` (green; hover shows guard status and the last self-check) or `DEMO · synthetic data` (amber).
- **Run selector:** every analytical page is scoped to a run through the `?run=` search param. Changing runs keeps the same filters.

**Routes:**
- `/login`
- `/` overview
- `/ingest`, `/ingest/$datasetId`
- `/triage`, `/leads/$leadId`
- `/investigate`, `/replay/$txid`
- `/actors/$ref`, `/entities/$ref`, `/addresses/$addr`, `/tx/$txid`, `/ips/$ip`
- `/geo`, `/flows`
- `/cases`, `/cases/$caseId`, `/verify`
- `/lab/scenarios`, `/lab/evaluations/$id`, `/lab/redteam`, `/lab/planner`, `/lab/academy`
- `/govern/models`, `/govern/drift`, `/govern/users`, `/govern/settings`, `/govern/audit`, `/govern/refdata`, `/govern/system`

## 10.4 The screens

### Overview
Run summary: volume, time span, sensors, observation model. Leads by grade and type, families distribution, **top 5 leads**, a mini geo map, *new/changed since last run*, drift banner, X-ray link. Everything is clickable into the filtered queue.

### Ingest
1. **Dropzone.** Multi-file, formats detected per file.
2. **Mapping wizard.** Source columns on the left, canonical fields on the right, auto-mapper confidence per field, 20-row normalised preview, save as profile.
3. **Live progress.** An I01–I06 stepper (SSE).
4. **X-ray.** Capability panel, observation model with its evidence, amount-unit decision with its evidence, field coverage, reject table filterable by rule, warnings, **"Run analysis"**.

### Triage (the analyst's home)
- **Virtualised queue** columns: GradeBadge with FamilyChips, type, title, ConfidenceBar(p), priority, value, last activity, status, assignee.
- **Filters:** type, grade, family, status, min p, text. **Saved views.**
- **Right-side preview panel.**
- **Keyboard:** `J/K` move, `Enter` open, `C` confirm, `D` dismiss (reason picker), `E` escalate, `S` snooze, `A` assign, `X` select, `⇧X` select range.
- **Bulk actions.** A "changed since review" badge.

### Lead detail
The nine tabs of §8.1. An action bar (confirm / dismiss with reason / escalate / assign / snooze / add to case). *Open in canvas* and *Replay* buttons. Every number has a provenance popover (method, model version, evidence refs).

### Investigate (link analysis)
- **Canvas.** Cytoscape with compound nodes (addresses inside entities inside actors).
- **Controls:**
  - expand by edge type;
  - filter by **method** and **minimum confidence**;
  - **time slider** (edges filtered by time);
  - layouts: fcose, breadthfirst for chains, concentric around a subject.
- **Path finder panel.** From and to pickers, *k*, max hops.
- **Node inspector.** Pin to case. Export PNG or GraphML.
- **Overview mode.** Above ~2,000 nodes, switches to the Sigma WebGL overview.

### Replay — the signature screen
```
┌ Replay · tx 9c1e…  ─────────────────────────────────────────────────── ▶ 1×  ⏮ ⏭ ────────────────────┐
│  NETWORK (observed)                                                   │ ORIGIN ESTIMATE              │
│    ◆ sensors   ○ candidates   ── announcements (animated by time)     │ 49.36.x.x:51544  ███████▌ .81│
│         ○──→◆S12   ○──→◆S07        t = +0.8 s  S12 hears it first     │ 185.220.x.x (Tor)  █ .06     │
│              from 49.36.x.x (AS55836 Reliance Jio, IN)                │ not observable     ▌ .07     │
│                                                                       │ first-spy says: 49.36.x.x    │
├───────────────────────────────────────────────────────────────────────┴──────────────────────────────┤
│  LEDGER   bc1q…(0.42 BTC) ──► [tx 9c1e…] ──► bc1q… 0.031 BTC (peel → EXD deposit)                    │
│                                          └─► bc1q… 0.3885 BTC (change → hop 7 of 23)                  │
│  timeline ├──────●─────────────────────────────────────────────────────────────────────────────┤ 12 s  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Top:** the observed peer graph (sensors and candidates) with announcements animated at their real relative times.
- **Right:** the posterior bars updating at each checkpoint, plus `p(unobservable)`.
- **Bottom:** the ledger strip showing what the money did.
- **Captions** narrate the events.
- **Keys:** `Space` play/pause, `←/→` step.

### Dossiers
**Actor** header: grade, p, families, value, first/last activity, timezone. Tabs:
- **Membership:** entities and addresses, each with membership evidence; merge suggestions with accept/reject for leads.
- **Network:** IPs, sessions, ASNs, countries, control p.
- **Money:** in/out Sankey, counterparties, cash-outs.
- **Patterns:** chains, CoinJoins, motifs.
- **Timeline:** activity histogram with the inferred offset.
- **Leads & cases.**

**Address, TX, IP and Session pages** show the same data at their own grain. For example, the TX page shows inputs and outputs, previous and next flows, CoinJoin score, origin candidates and anomaly. The IP page shows enrichment **with source and as-of date**, role, sessions, entities controlled and crowdedness.

### Geo and Flows
- **Geo:** a deck.gl world map. `ArcLayer` flows between countries (width = value, colour = taint) and origin points aggregated by ASN, filterable by run, lead, family and time.
- **Flows:** an ECharts Sankey from any root (actor or seed), depth ≤ 4.

### Cases, Export, Verify
- **Case workspace:** items board, Markdown notes, case timeline (from audit), export panel (evidence pack / MISP / STIX / GraphML / i2 CSV / PDF), approval state.
- **Verify:** drag a pack → progress → **green or red seal** with the full report (§9.3.7).

### Lab and Academy
- **Scenario Studio:** preset picker, parameter form with ranges, adversary-knob sliders, seed, generate, then the realism report.
- **Evaluations:** metric cards with CIs against baselines, calibration plot, per-pack table, confusion matrices.
- **Red-team:** robustness curves per knob.
- **Planner** `[STRETCH]`: strategy and K slider → attribution-accuracy curve plus a sensor map.
- **Academy:** challenge list, timer, question UI (pick an IP, actor or exchange from searchable lists), score, leaderboard, *watch the engine solve it*.

### Govern
- **Models:** registry, model cards, metrics, promote/rollback, shadow comparison.
- **Drift:** feature × PSI heat map.
- **Users & roles.**
- **Settings:** grouped, with defaults and "changed from default".
- **Audit:** table plus a **Verify chain** button → seal.
- **Reference data:** source, licence, as-of, import.
- **System:** mode, version, **offline status** (guard active, egress test result, last self-check), storage, job queue.

## 10.5 The design system — tokens

Dark "ops console" by default for long analyst sessions, and a light theme for printing and reports. Tokens live in `packages/tokens/tokens.css` and are consumed by the web app and the site.

```css
:root[data-theme="dark"] {
  --bg: #0B0F14;  --surface: #111821;  --surface-2: #17202B;  --border: #243041;
  --text: #E6EDF3;  --text-muted: #8B98A9;  --focus: #7DD3FC;
  --brand: #F59E0B;            /* saffron accent — actions, active nav */
  --fam-net:   #22D3EE;  --fam-flow: #A78BFA;  --fam-taint: #F87171;
  --fam-anom:  #FBBF24;  --fam-behav: #34D399;
  --grade-a: #EF4444;  --grade-b: #F59E0B;  --grade-c: #EAB308;
  --ok: #22C55E;  --warn: #F59E0B;  --err: #EF4444;
  --radius: 6px;  --space: 4px;                         /* 4-px grid */
  --font-sans: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}
:root[data-theme="light"] { --bg:#FFFFFF; --surface:#F7F8FA; --text:#0B1220; /* … */ }
```

- **Type scale:** 12 / 13 / 14 / 16 / 20 / 24. **Tabular numerals** everywhere numbers align.
- **Density:** *comfortable* and *compact* (queue rows 36 → 28 px).
- **Colour is never the only carrier of meaning** (colour-blind safety):
  - Grades are **A = solid badge, B = outlined, C = dashed outline**, and always carry their letter.
  - Families are chips with icon plus code.

## 10.6 Encoding confidence and provenance on the canvas

| Visual channel | Encodes |
|---|---|
| **Line style** | Method class: **solid** = observed (`obs`, `prevout`) · **dashed** = model (`origin_model`, `er_model`, `change_model`) · **dotted** = heuristic (`cioh`, `addr_amount_match`) · **double** = analyst assertion |
| Opacity and width | Confidence (p → 0.25–1.0 opacity, 1–4 px) |
| Colour | Evidence family of the edge |
| Node shape | IP = hexagon · SESSION = small hexagon · TX = square · ADDRESS = circle · ENTITY = rounded rectangle (compound) · ACTOR = large compound · SERVICE = octagon · SENSOR = triangle |
| Badges on nodes | Tor / VPN / hosting / bogon / seed / CASHOUT / victim-like |
| Identifiers | Mono font, middle truncation (`bc1q8f…k2d7`), copy button, full value on hover |

Hovering any edge opens the **EnvelopePopover**: method, confidence, model version, run and evidence refs, with a *show source rows* link. That popover is the evidence story in one gesture.

## 10.7 Keyboard and ⌘K

| Keys | Action |
|---|---|
| `⌘K` / `Ctrl K` | Omnibox. Paste any txid, address, IP, ASN or actor ref; the type is detected and you jump there. Also runs commands ("go to triage", "new case", "verify pack"). |
| `G then T/I/C/L/V` | Go to Triage / Investigate / Cases / Lab / Govern |
| `J / K`, `Enter`, `C`, `D`, `E`, `S`, `A` | Triage (§10.4) |
| `F` | Focus filter |
| `?` | Shortcut sheet |
| `Space`, `← / →` | Replay play/pause, step |

## 10.8 Language and formatting

- **English and हिंदी** for all UI chrome (navigation, buttons, headers, statuses, reason templates). Identifiers and data stay as-is. The language switcher is in the user menu. The `hi` catalogue is reviewed by a native speaker on the team.
- **Time:** `21 Nov 2026, 14:32:07 IST (UTC+05:30)` by default, with a UTC toggle. Relative times ("3 h ago") always have the absolute time on hover.
- **Money:** `0.41235678 BTC`, with a sats toggle. Large values abbreviated (`14.02 BTC`). Never a float round-trip (formatting from integer sats).

## 10.9 Offline assets and performance budgets

| Rule | Budget / mechanism |
|---|---|
| No external URL in the bundle (I11) | `scripts/check-no-external-urls.mjs` scans `dist/`, with an allowlist of none |
| No external request at runtime | Playwright `test_web_makes_no_external_requests` fails on any request whose host ≠ app host |
| Fonts | Fontsource-imported IBM Plex, `woff2` in `dist/` |
| Map data | `ne_110m_admin_0_countries.json` (Natural Earth, public domain), bundled |
| Initial JS (shell) | ≤ 350 KB gzip `[DEFAULT]`, route-level code splitting (canvas, deck.gl and ECharts load on demand) |
| Canvas | 60 fps interaction at ≤ 2,000 elements; beyond that, Sigma overview |
| Tables | Virtualised; 100k rows scroll smoothly |
| Layout | ForceAtlas2 in a Web Worker; never on the main thread |
| CSP | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; worker-src 'self' blob:; connect-src 'self' <api-origin>; frame-ancestors 'none'; base-uri 'none'` |

## 10.10 Empty, loading, error and special states

- **Loading:** skeletons shaped like the final content. No spinner longer than 300 ms without one.
- **Empty:** says *why* ("No ACTOR leads in this run. 3 CHAIN leads exist.") and offers the next action.
- **Error:** surfaces the RFC 9457 `title` and `detail` plus a retry. Unexpected errors show a reference ID that matches the server log line.
- **Snapshot mode (demo only):** if the API is unreachable, the app switches to the bundled pre-computed snapshot of the hero run, read-only, with an amber banner *"Live API unavailable — showing a recorded snapshot."* The demo can never show a broken page (§12.7).
- **Drift banner:** "Scored under drift — see Govern → Drift".
- **Demo banner:** "Synthetic data only. Uploads are deleted after 60 minutes. The sandbox resets nightly at 03:00 IST."

---


# PART 11 — EVALUATION, RED-TEAM & THE METRICS PAGE (M6)

> We will be judged against 499 teams claiming "99% accuracy". Our answer is to **publish every number, on worlds the models never saw, with confidence intervals, against the baselines we claim to beat, regenerated by CI on every change**. Including where we fail.

## 11.1 Metric definitions

| Metric | Definition | Used for |
|---|---|---|
| **precision@k / recall@k** | Among the top-k leads by priority, the share that are truly illicit (and the share of all illicit actors found) | Lead ranking, the headline number |
| **PR-AUC** | Area under the precision–recall curve on actors | Ranker quality under imbalance |
| **ECE** | Expected Calibration Error, 10 equal-width bins of p | "Confidence means what it says" |
| **Per-wallet precision / recall** (clustering) | For each labelled address *a*: precision = \|C(a) ∩ T(a)\| / \|C(a)\|, recall = \|C(a) ∩ T(a)\| / \|T(a)\|, averaged, where C = predicted cluster and T = true owner's addresses. Also reported **per entity**. This follows Müller et al. 2026's recommendation over pairwise metrics. | CIOH, change merges, ER |
| Pairwise P/R, ARI, NMI | Standard clustering agreement | Comparison with prior literature |
| **Attribution top-1 / top-3** | On transactions whose origin *was observable*, the share where the true origin (ip, session) is the model's top-1 / in its top-3 | Origin model vs first-spy |
| **Coverage** | Share of all transactions with p_top ≥ 0.5 | How much the network layer actually tells us |
| **Unobservability AUROC** | AUROC of `p_unobservable` against truth "origin not observable" | Honest abstention |
| CoinJoin macro-F1 · batch-payout FP rate | Over mixing classes / on truth batch payouts | `coinjoin_clf` |
| Change precision@0.95 | Precision of merges made at the merge threshold | `change_clf` |
| **Chain recall** | A truth laundering chain counts as detected if ≥ 80% of its hops lie in one predicted chain with p ≥ τ | `peel_scorer` |
| **CASHOUT P/R** | Against truth "deposit address of an illicit customer" | Most actionable output |
| Victim FP rate | Share of truth victims that appear as ACTOR leads | Victim/perpetrator separation |
| Runtime, throughput | Wall time per stage and end to end · rows per second | §14.3 |

## 11.2 Protocol

- **Worlds:** `test-rand` (10 frozen seeds), plus every stress pack, plus the hero world (reported separately and **never** used for tuning).
- **Confidence intervals:** 95% bootstrap CIs **over worlds** (resampling worlds, not rows).
- **Breakdowns:** by observation model (vantage / flow / mixed / single / none).
- **Baselines computed on the same worlds:**
  - first-spy and first-sender;
  - the rule-only CoinJoin detector;
  - plain CIOH;
  - taint-only ranking;
  - the classic change heuristic.
- **The report** is `reports/eval-<version>.json` plus a rendered HTML page on the site. It carries the generator version, the model versions and the git SHA.

## 11.3 Targets (initial, `[DEFAULT]`)

| Area | Target |
|---|---|
| Lead ranking | precision@50 ≥ 0.80 · PR-AUC ≥ 0.70 · ECE ≤ 0.05 |
| Origin | top-1 ≥ first-spy + 15 pts (vantage) · ECE ≤ 0.05 · unobservability AUROC ≥ 0.85 |
| Clustering | CIOH per-wallet precision ≥ 0.90 on synthetic · ER: +10 pts per-wallet recall at ≤ 2 pts precision loss |
| Patterns | CoinJoin macro-F1 ≥ 0.95, batch FP ≤ 1% · chain recall ≥ 0.90 (≥ 5 hops) · change precision@0.95 ≥ 0.99 |
| Actionability | CASHOUT precision ≥ 0.80 · victim FP ≤ 2% |
| Runtime | hero world upload → published ≤ 10 min on the reference laptop |

Targets are reviewed **once**, after the first full evaluation (end of P4), and frozen. Every change goes in the decision log. A target moved after seeing test results must say so.

## 11.4 Regression gates in CI

| Trigger | Worlds | Gate |
|---|---|---|
| Pull request | `tiny` + 2 small `val-rand` worlds (cached) | No headline metric drops > 5 pts vs `reports/baseline.json`. Determinism test. Runtime ≤ 1.5× baseline. |
| Push to `main` · nightly | full `test-rand` + stress packs | Publishes the report. Opens an issue if any target is missed. |
| Model promotion | `test-rand` | §7.5 gate (I14) |

## 11.5 Red-team sweeps (Adversary mode)

For each adversary knob (§5.7), we sweep values {0, 0.25, 0.5, 0.75, 1.0} × 3 seeds on a mid-size world. We re-run the engine and record every headline metric. The output is a robustness curve per knob plus the **break point**, the knob value at which the headline metric falls below 50% of its no-adversary value.

The red-team page leads with the honest summary, for example: *"Origin attribution degrades gracefully with Tor share up to ~0.4; onion-only broadcasting makes origin unobservable (by design, `p_unobservable` rises accordingly); CIOH is robust to cluster-splitting only when co-origin evidence exists."*

## 11.6 Sensor-coverage planner `[STRETCH]`

- **Question it answers for NTRO:** *where should we listen?*
- **Input:** a world's `arrivals.npz` (arrival times at **all** nodes for a sample of ~2,000 transactions).
- **Method:** candidate sensor sets are chosen by a strategy:
  - random;
  - top-degree listeners;
  - ASN-diverse;
  - **greedy marginal gain** (add the sensor that most improves validation attribution accuracy, repeat to K).

  For each set, observations are re-derived *from the stored arrival times* (cheap, no re-simulation) and the origin model is re-run.
- **Output:** attribution accuracy and coverage vs K per strategy, plus a map of chosen sensors by ASN and country.
- **Why it is credible:** `origin_ranker` is trained across randomised sensor sets (§5.11), so it is valid for sensor sets it never saw.

## 11.7 The metrics page

- **Location:** `apps/site` renders `src/data/metrics/latest.json` and the history of previous reports (kept in git).
- **Contents:** cards with CIs and baselines, calibration plots, per-pack tables, robustness curves, runtime benchmarks, the commit SHA and generation time, and links to the raw JSON.
- **Updates:** CI commits the new JSON to `main` (`[skip ci]`), which redeploys the site on Vercel (§12.8).
- **Headline to link from the deck:** *"Every number on this page was produced by CI from the commit shown, on worlds the models never saw."*

## 11.8 Academy scoring

- **Challenges:** built from `academy-01…05` worlds. Each has 3–6 questions with typed answers:
  - pick the operator's IP;
  - pick the actor behind a seed;
  - pick the cash-out service;
  - pick the second wallet;
  - estimate the timezone.
- **Answer keys** are derived from truth **in the worker, never sent to the browser**. Scoring is server-side.
- **Score** = correct answers plus a time bonus. Leaderboard per challenge.
- **"Watch the engine solve it"** opens the engine's top lead and its evidence for the same question, which is the human-vs-machine moment for the finale.

---


# PART 12 — DEPLOYMENT, ENVIRONMENTS & DEVOPS

## 12.1 Repository layout (complete)

```
sih26146/                                   ← monorepo root (this directory)
├── SUTRADHAR_PLATFORM_BLUEPRINT.md         ← this document
├── README.md                               quick start · architecture diagram · badges · links
├── Makefile                                make dev | test | lint | e2e | bundle | demo-data
├── pyproject.toml  uv.lock                 uv workspace (members: apps/api, packages/*)
├── package.json  pnpm-workspace.yaml  pnpm-lock.yaml
├── .importlinter  ruff.toml  pyrightconfig.json  .editorconfig  .pre-commit-config.yaml
├── apps/
│   ├── api/        pyproject.toml · sutradhar_api/{main.py, routers/, services/, readers/, auth/, jobs/, audit.py, offline_guard.py, sse.py, settings.py, db/, migrations/}
│   ├── web/        package.json · vite.config.ts · vercel.json · src/ (Part 10)
│   └── site/       package.json · astro.config.mjs · vercel.json · src/{content/docs/, data/metrics/, pages/}
├── packages/
│   ├── schemas/    sutradhar_schemas/{contract.py, manifest.py, lead.py, envelope.py, profile.py}
│   ├── engine/     sutradhar_engine/{ingest/, stages/e01_load.py … e19_publish.py, models/, explain/, store/ddl.sql, digest.py, sdk.py, context.py}
│   ├── generator/  sutradhar_gen/ (Part 5)
│   ├── evals/      sutradhar_evals/{truth.py, metrics.py, report.py, redteam.py, planner.py, academy.py, train.py}
│   ├── cli/        sutradhar_cli/main.py (Typer)
│   ├── plugins/    sutradhar_plugins/{peel.py, coinjoin_rules.py, motifs/}
│   ├── ts-client/  generated types + client
│   └── tokens/     tokens.css
├── models/         <name>/<version>/… (Part 7.5)
├── refdata/        manifest.json (+ gitignored snapshots, fetched by CI)
├── deploy/
│   ├── docker/     api.Dockerfile · web.Dockerfile · demo.Dockerfile
│   ├── caddy/      Caddyfile
│   ├── compose/    compose.dev.yaml · compose.airgap.yaml · compose.offline-test.yaml · db-init/01-roles.sql
│   ├── airgap/     install.sh · selfcheck.sh · upgrade.sh · uninstall.sh · make-bundle.sh · README-AIRGAP.txt
│   └── render/     render.yaml
├── docs/           INVARIANTS.md · requirements.csv · adr/NNNN-*.md · technical-writeup.md · runbooks/ · model-cards/
├── scripts/        check-no-external-urls.mjs · fetch-refdata.sh · gen-client.sh · bench.py
└── .github/workflows/  ci.yml · eval.yml · images.yml · deploy.yml · release.yml · nightly.yml
```

## 12.2 Environments and modes

| | `dev` | `ci` | `demo` (cloud) | `airgap` (product) |
|---|---|---|---|---|
| Where | Laptop | GitHub Actions | Vercel + Render | Any Linux host |
| App DB | Postgres (compose) | Postgres service container | **SQLite**, reseeded at boot | Postgres 17 |
| Worker | Separate process | Separate | **Embedded** (1 subprocess) | Separate container (concurrency 2) |
| Offline guard | off (warn) | **on** | **on** | **on** |
| Data | Anything | Generated worlds | Baked hero world + capped uploads | Anything |
| Auth | Local users | Test users | "Enter demo" + admin | Local users (bootstrap admin at install) |
| Uploads | Unlimited | – | ≤ 25 MB, TTL 60 min | Unlimited |
| Reset | – | – | Nightly 03:00 IST | – |
| Snapshot fallback | – | – | **on** | – |
| Swagger UI | on | – | on (read-only) | on |

## 12.3 Configuration

- **Environment variables** configure *the deployment*: mode, URLs, secrets, paths, threads. The full table is in §17.2.
- **Settings** (the `settings` table, editable in Govern, audited) configure *the analysis*: thresholds, weights, windows. Defaults are in §17.3.
- **Rule:** a threshold never lives in an environment variable. A secret never lives in settings.

## 12.4 Container images

```dockerfile
# deploy/docker/api.Dockerfile  (outline — pin every base by digest)
FROM python:3.12-slim-bookworm@sha256:<pinned> AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*                       # WeasyPrint runtime libs
COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --package sutradhar-cli     # workspace member with all runtime deps
COPY models /models
COPY refdata/snapshots /refdata                            # DB-IP country+ASN, Tor, VPN, DC lists (dated)
COPY deploy/fonts/ibm-plex /usr/share/fonts/ibm-plex       # for PDF reports
RUN useradd -r -u 10001 sutradhar && mkdir -p /data && chown 10001 /data
USER 10001
EXPOSE 8000
ENTRYPOINT ["/app/.venv/bin/sutradhar"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# deploy/docker/web.Dockerfile
FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /repo
COPY . .
RUN pnpm install --frozen-lockfile && pnpm --filter @sutradhar/web build
FROM caddy:2-alpine@sha256:<pinned>
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /repo/apps/web/dist /srv
```

```dockerfile
# deploy/docker/demo.Dockerfile — the showroom image
ARG BASE
FROM ${BASE}                                   # ghcr.io/<owner>/sutradhar-api:<sha>
COPY --chown=10001 demo-data/ /demo-seed/      # hero + 3 scenarios, pre-analysed; demo_seed.sqlite
ENV APP_MODE=demo EMBEDDED_WORKER=true DATA_DIR=/data DATABASE_URL=sqlite:////data/app.sqlite
# at boot: copy /demo-seed → /data (fresh), then serve. Nightly reset repeats the copy.
```

**Architectures.** `linux/amd64` is required. `linux/arm64` is built on release tags (buildx + QEMU; every dependency ships arm64 wheels), so Apple-silicon laptops can run the bundle in Docker.

## 12.5 Air-gapped deployment (the product)

### 12.5.1 `compose.airgap.yaml`

```yaml
name: sutradhar
x-app-env: &app-env
  APP_MODE: airgap
  DATABASE_URL: postgresql+psycopg://sutradhar_app:${APP_DB_PASSWORD}@db:5432/sutradhar
  MIGRATION_DATABASE_URL: postgresql+psycopg://sutradhar_owner:${OWNER_DB_PASSWORD}@db:5432/sutradhar
  DATA_DIR: /data
  MODELS_DIR: /models
  REFDATA_DIR: /refdata
  REFDATA_OVERRIDE_DIR: /refdata-override
  JWT_SECRET: ${JWT_SECRET}
  OFFLINE_GUARD: "on"
  ENGINE_THREADS: ${ENGINE_THREADS:-8}

services:
  web:
    image: sutradhar-web:${VERSION}
    ports: ["${BIND:-127.0.0.1}:8080:8080"]
    networks: [edge, app]                       # the ONLY service with a host-reachable network
    depends_on: { api: { condition: service_healthy } }
    read_only: true
    tmpfs: [/data, /config]                     # caddy storage dirs; nothing persists
    restart: unless-stopped
  api:
    image: sutradhar-api:${VERSION}
    command: ["serve", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
    environment: *app-env
    volumes: [data:/data, refdata_override:/refdata-override:ro]
    networks: [app]
    depends_on: { db: { condition: service_healthy } }
    healthcheck: { test: ["CMD", "sutradhar", "health", "--local"], interval: 10s, timeout: 5s, retries: 12 }
    restart: unless-stopped
  worker:
    image: sutradhar-api:${VERSION}
    command: ["worker", "--concurrency", "${WORKER_CONCURRENCY:-2}"]
    environment: *app-env
    volumes: [data:/data, refdata_override:/refdata-override:ro]
    networks: [app]
    depends_on: { db: { condition: service_healthy } }
    restart: unless-stopped
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: sutradhar
      POSTGRES_USER: sutradhar_owner
      POSTGRES_PASSWORD: ${OWNER_DB_PASSWORD}
      APP_DB_PASSWORD: ${APP_DB_PASSWORD}         # read by db-init/01-roles.sh to create sutradhar_app
    volumes: [pgdata:/var/lib/postgresql/data, ./db-init:/docker-entrypoint-initdb.d:ro]
    networks: [app]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U sutradhar_owner -d sutradhar"], interval: 5s, timeout: 5s, retries: 20 }
    restart: unless-stopped

networks:
  edge: {}
  app: { internal: true }                       # no default route — application tier cannot egress

volumes: { pgdata: {}, data: {}, refdata_override: {} }
```

**Two database roles.**
- `sutradhar_owner` runs migrations.
- `sutradhar_app` is what the API and worker use. It is created by `db-init/01-roles.sh` with DML grants only and **no `UPDATE/DELETE/TRUNCATE` on `audit_log`**.

So I5 holds against the application's own credentials, not just in code.

### 12.5.2 `Caddyfile`

```caddyfile
{
	admin off
	auto_https off
	persist_config off
}
:8080 {
	encode zstd gzip
	header {
		Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "no-referrer"
		X-Frame-Options "DENY"
		Permissions-Policy "geolocation=(), camera=(), microphone=()"
		-Server
	}
	handle /api/* {
		reverse_proxy api:8000 {
			flush_interval -1          # stream SSE immediately
		}
	}
	handle {
		root * /srv
		try_files {path} /index.html
		file_server
	}
}
```

### 12.5.3 The bundle and the installer

```
sutradhar-airgap-1.0.0-linux-amd64/
├── images/                 sutradhar-api.tar.zst · sutradhar-web.tar.zst · postgres-17-alpine.tar.zst
├── compose.airgap.yaml  .env.example  db-init/01-roles.sh
├── install.sh  selfcheck.sh  upgrade.sh  uninstall.sh
├── samples/                hero-ghostline (CSV + JSON + XML) · schema-zoo · watchlist.csv
├── docs/                   technical-writeup.pdf · model-cards/ · user-guide.pdf · README-AIRGAP.txt
├── sbom/                   api.spdx.json · web.spdx.json
└── SHA256SUMS              (and SHA256SUMS.sig if signing is enabled)
```

**`install.sh` does:**
1. Check Docker ≥ 24 and Compose v2. Check free disk ≥ 20 GB.
2. `sha256sum -c SHA256SUMS`. **Refuse to continue on any mismatch.**
3. `docker load` each image.
4. Create `.env` from `.env.example` with random secrets (`openssl rand`).
5. Start `db`; run `sutradhar migrate` (as owner); create the admin (printed once, must be changed on first login).
6. Start everything. Run `selfcheck.sh`:
   - health endpoints;
   - **egress test** (the API container attempts to connect to a public IP and must fail);
   - a tiny-world run end to end;
   - audit chain verify.
7. Print `http://127.0.0.1:8080`.

**Target: fresh machine to hero demo in ≤ 15 minutes** (R-PLT-002).

**Release asset size.** GitHub release assets are limited to 2 GiB each. `make-bundle.sh` splits the archive (`split -b 1900M`) if needed, and `install.sh` reassembles it.

## 12.6 The cloud showroom

### 12.6.1 Vercel (two projects from one repo)

| Setting | `sutradhar-web` | `sutradhar-site` |
|---|---|---|
| Root directory | `apps/web` | `apps/site` |
| Framework preset | Vite | Astro |
| Install command | `pnpm install --frozen-lockfile` | same |
| Build command | `pnpm build` | `pnpm build` |
| Output | `dist` | `dist` |
| Env | `VITE_API_BASE_URL=https://<api>.onrender.com` · `VITE_APP_MODE=demo` | – |
| Ignored build step | `git diff --quiet HEAD^ HEAD -- . ../../packages/ts-client ../../packages/tokens` | `git diff --quiet HEAD^ HEAD -- . ../../packages/tokens` |
| Previews | per PR (CORS allows the preview pattern, §12.6.3) | per PR |
| Plan | Hobby (non-commercial use; fine for SIH) | Hobby |

```json
// apps/web/vercel.json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [
    { "source": "/(.*)", "headers": [
      { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; worker-src 'self' blob:; connect-src 'self' https://<api>.onrender.com; frame-ancestors 'none'; base-uri 'none'" },
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "Referrer-Policy", "value": "no-referrer" },
      { "key": "X-Frame-Options", "value": "DENY" } ] },
    { "source": "/assets/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] }
  ]
}
```

### 12.6.2 Render (the demo API)

```yaml
# deploy/render/render.yaml  (Blueprint; verify field names against render.com/docs/blueprint-spec on first use)
services:
  - type: web
    name: sutradhar-api-demo
    runtime: image
    image:
      url: ghcr.io/<owner>/sutradhar-api-demo:main
      creds:
        fromRegistryCreds:
          name: ghcr                 # workspace registry credential: GitHub username + PAT (read:packages)
    plan: standard                   # 1 CPU / 2 GB · paid plans never spin down
    region: singapore                # nearest Render region to India
    healthCheckPath: /api/health
    envVars:
      - key: APP_MODE
        value: demo
      - key: EMBEDDED_WORKER
        value: "true"
      - key: JWT_SECRET
        generateValue: true
      - key: DEMO_ADMIN_PASSWORD
        sync: false                  # set in dashboard
      - key: CORS_ORIGINS
        sync: false                  # https://sutradhar-web.vercel.app[,https://app.<domain>]
      - key: CORS_ORIGIN_REGEX
        sync: false                  # ^https://sutradhar-web-[a-z0-9-]+-<team>\.vercel\.app$
```

**Deploying a new image.** Image-backed services do not auto-redeploy when a tag moves. CI calls the service's **deploy hook** with `imgURL` set to the new tag (URL-encoded). Render requires every part except the tag or digest to match the service's configured image URL:

```bash
curl -fsS -X POST "${RENDER_DEPLOY_HOOK}&imgURL=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=""))' "ghcr.io/<owner>/sutradhar-api-demo:${GITHUB_SHA}")"
```

**Why these choices** (verified September 2026):

| Plan | Facts | Verdict |
|---|---|---|
| Render **Free** | 0.1 CPU / 512 MB; spins down after 15 min idle and takes about a minute to wake; free Postgres **expires after 30 days** | ✗ A judge would see a loading page, and the database would expire before the finale |
| Render **Standard** | 1 CPU / 2 GB, $25/month, never spins down | ✓ **Chosen** |
| Railway **Hobby** | $5/month incl. $5 usage, then usage-billed (~$10/GB-RAM-month, ~$20/vCPU-month) | ✓ **Documented alternative.** Cheaper if memory stays low. The team has used it before. Deploy the same GHCR image with the same env. |
| Vercel Functions for the API | Hobby: 2 GB / 1 vCPU, 300 s max, 4 active CPU-h/month included | ✗ Request-scoped; wrong shape for a stateful graph engine (§3.2) |
| Hugging Face Spaces (Docker) | 2 vCPU / 16 GB, but Docker Spaces need a paid plan and free hardware sleeps after 48 h idle | ✗ Not needed |

### 12.6.3 CORS, domains, auth across sites
- **CORS:** the API allows `CORS_ORIGINS` exactly, plus `CORS_ORIGIN_REGEX` for Vercel previews. Credentials are **not** used (bearer tokens), so `Access-Control-Allow-Credentials` stays off.
- **Custom domain `[OPEN]`:** optional (`app.<domain>` → Vercel, `api.<domain>` → Render). With one registrable domain the two are same-site, which is tidier but not required.
- **SSE** goes **directly** to the API origin. It is never proxied through Vercel rewrites (long streams and proxies do not mix).

## 12.7 Demo-mode hardening — why the link feels production-grade

| Measure | Detail |
|---|---|
| Warm by construction | Paid instance (no sleep). The hero world is **baked into the image** and pre-analysed, so the first request is fast. |
| **Snapshot fallback** | The SPA ships a compressed snapshot of the hero run. If `/api/health` fails twice, the UI switches to read-only snapshot mode with a banner. **The link cannot show a broken page.** |
| Upload limits | ≤ 25 MB, ≤ 200 k rows, 2 concurrent jobs, TTL 60 min then purged (I19). Watermarked exports ("DEMO — SYNTHETIC"). |
| Rate limits | Per IP: 60 requests/min general, 5 uploads/hour, 20 demo logins/hour |
| Nightly reset | 03:00 IST: restore `/demo-seed`, fresh SQLite, purge uploads. A banner warns 10 minutes before (`demo.reset_soon`). |
| Monitoring | UptimeRobot (or BetterStack) checks `/api/health` every 5 min. A status badge sits on the landing page. |
| No outbound calls | The offline guard is on in demo too. The showroom has no third-party calls at all, so no analytics scripts, no error-reporting SaaS. |
| Admin surface | Only `/demo/reset` and read-only Govern. User management is disabled in demo mode. |

## 12.8 CI/CD workflows

| Workflow | Trigger | Jobs | Duration target |
|---|---|---|---|
| `ci.yml` | PR, push | **py** (ruff, pyright, import-linter, pytest on `tiny`) · **js** (eslint, tsc, vitest, build, `check-no-external-urls`, ts-client up to date) · **offline-engine** (`docker run --network none … sutradhar selftest --scenario tiny`) · **e2e** (compose `offline-test` profile + Playwright) · quick eval gate | ≤ 15 min |
| `eval.yml` | push `main`, nightly, manual | Restore/generate cached worlds (key = generator version + seeds) → engine → metrics → gates → commit `apps/site/src/data/metrics/latest.json` `[skip ci]` → site redeploys | ≤ 60 min |
| `images.yml` | push `main`, tags | buildx api/web/demo · push GHCR `:<sha>` and `:main` · **syft SBOM** · **grype scan** (fail on critical) | ≤ 25 min |
| `deploy.yml` | after `images` on `main` | Render deploy hook with `imgURL=…:<sha>` · wait for `/api/health` · smoke test through the Vercel URL | ≤ 5 min |
| `release.yml` | tag `v*` | Bundle (images, models, refdata, samples, docs PDF, SBOMs, SHA256SUMS) · **bundle smoke test with networking disabled for the app tier** · GitHub Release | ≤ 60 min |
| `nightly.yml` | cron | Refresh refdata snapshots (DB-IP monthly, Tor exits, X4BNet) → PR if changed · purge old CI artefacts and old image versions (retention: last 3 per image) | ≤ 10 min |

**CI minutes and package storage `[RISK]`.** Private repositories on free GitHub plans have limited Actions minutes and Packages storage. Mitigations:
- path filters, caching (uv, pnpm, Docker layers, generated worlds), and `concurrency: cancel-in-progress`;
- full evaluation nightly rather than per PR;
- image retention of the last 3 versions;
- **GitHub Pro via the Student Developer Pack** for the repository owner;
- making the repository and images public at feature freeze `[DEFAULT]`, which removes both limits.

## 12.9 Proving "offline" — the verification suite

| Check | How | Where |
|---|---|---|
| In-process guard | `offline_guard.install()` wraps `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo`, allowing only loopback, RFC 1918 compose ranges and Unix sockets. Anything else raises `OfflineViolation` and is logged. | API and worker start-up in `demo`/`airgap` |
| Guard unit test | Attempt `1.1.1.1:443` → `OfflineViolation` | `test_offline_guard_blocks_public` |
| Engine without a network | `docker run --network none sutradhar-api:<sha> selftest --scenario tiny` (generate → ingest → run → verify pack) | CI `offline-engine` |
| Whole stack without egress | `compose.offline-test.yaml`: every service on `internal: true`, plus a Playwright container on the same network running the analyst journey, **asserting that no request left the app host** | CI `e2e` |
| Bundle scan | Grep the built SPA and the Python site-packages for hard-coded telemetry endpoints (allowlist-reviewed) | `release.yml` |
| Developer check (Arch) | `unshare -rn sutradhar selftest --scenario tiny` (unprivileged user and network namespace) | Local |

## 12.10 Observability

- **Logs:** structured JSON logs (`structlog`) with `request_id`, `user_id`, `job_id`, `run_id` and `stage` on every line. Logs never contain secrets or full uploaded rows.
- **Metrics:** Prometheus `/metrics` on the API's internal port (not proxied by Caddy). It covers request latency histograms, job durations by kind and stage, queue depth, ingest rows/s, and model inference counts.
- **System page:** mode, version, offline status, last self-check, storage, queue. An optional `ops` compose profile adds Prometheus and Grafana images to the bundle.

## 12.11 Backup and restore (air-gapped)

- **`sutradhar backup --out /backups/<ts>`:**
  - `pg_dump -Fc` of the app DB;
  - a manifest of `/data` (datasets, runs and exports are immutable, so an `rsync` copy is consistent);
  - `SHA256SUMS`.
- **`sutradhar restore /backups/<ts>`:** verify, restore the DB, then run `audit verify` and `selfcheck`.
- **P8 includes one timed restore drill.** The measured time is written into the runbook.

## 12.12 Cost (October → December)

| Item | Cost |
|---|---|
| Vercel Hobby (web + site) | ₹0 |
| Render Standard (demo API), ~3 months | ~$75 (≈ ₹6,500). *Railway alternative: ~$10–25/month depending on RAM actually used.* |
| GHCR, GitHub Actions | ₹0 with Student Developer Pack / public repo; else watch limits (§12.8) |
| Domain `[OPEN]` | Optional, ~₹500–1,000/year |
| UptimeRobot | ₹0 (free tier) |
| **Total** | **≈ ₹6,500–7,500**, all optional except the backend host |

---


# PART 13 — SECURITY, PRIVACY & LAWFUL USE

> This is an intelligence tool that links money to network endpoints. The first question from a serious evaluator will not be about F1 scores. It will be: *"who can see what, who changed what, and can this be misused?"* This part is the answer.

## 13.1 Assets and adversaries

| Asset | Why it matters |
|---|---|
| Ingested traffic datasets | Sensitive metadata (IPs, timings). In real use, the most sensitive thing on the machine. |
| Leads, dossiers, cases | Investigative hypotheses about people's infrastructure |
| Audit log | The integrity of everything else rests on it |
| Models and settings | Silent changes alter who gets flagged |
| Credentials and secrets | The keys to all of the above |
| The bundle itself | Supply-chain target |

| Adversary | Where |
|---|---|
| External attacker | Demo showroom (public). The air-gapped product has no network exposure beyond localhost/LAN by default. |
| Malicious or careless insider | Tampering with leads, deleting evidence, exfiltrating datasets |
| Malicious input file | XXE, billion laughs, decompression bombs, oversized records, CSV injection payloads |
| Supply chain | A compromised dependency or base image |
| Demo abuse | Uploading real personal data, scraping, resource exhaustion |

## 13.2 STRIDE, against this application

| Threat | Mitigation | Test |
|---|---|---|
| **Spoofing** | argon2id password hashes. JWT (HS256, 256-bit secret) with 20-minute access tokens. Rotating refresh tokens with reuse detection (revokes the whole session family). Login rate limit and lockout (5 failures → 15 min). | `test_refresh_reuse_revokes_family`, `test_login_lockout` |
| **Tampering** | Hash-chained audit with DB triggers **and** role grants (I5). Runs are immutable (I3). Models are SHA-checked at load. Bundle `SHA256SUMS`. Read-only model and refdata volumes. | `test_audit_tamper_detected`, `test_model_sha_mismatch_refuses_load` |
| **Repudiation** | Every mutation, export, download and verification is audited with actor and role (I13). Dossier and evidence-graph opens go to the access log. | `test_every_mutation_emits_audit` |
| **Information disclosure** | Role matrix (§2.4). Exports of escalated cases need lead approval. No third-party calls (I1). CSP. Logs never contain secrets or raw rows. **Demo is synthetic-only.** | `test_rbac_matrix`, `test_escalated_export_requires_approval` |
| **Denial of service** | Upload and row caps. Decompression-ratio guard. Parser depth and record-size limits (V20). Job concurrency caps. Per-IP rate limits (demo). Pagination everywhere (I12). | `test_zip_bomb_rejected`, `test_deep_json_rejected` |
| **Elevation of privilege** | A single `require()` gate. No self-role edits. Model promotion is admin-only and gated (I14). Plugins load only from installed entry points or the admin-controlled plugin directory, **never uploaded through the UI**. | `test_every_mutating_endpoint_declares_permission`, `test_cannot_change_own_role` |

## 13.3 Input handling

- **Uploads:**
  - streamed to disk under a server-generated name (the client filename is metadata only, so no path traversal);
  - magic-byte sniffing;
  - a single compressed member only (gzip/zstd), with the 200:1 ratio guard.
- **XML (I15):** `defusedxml` rejects DTDs, entities and external references. `lxml.iterparse(resolve_entities=False, no_network=True, huge_tree=False)`. The test fixtures include XXE and billion-laughs payloads.
- **JSON:** `ijson` streaming with depth ≤ 32 and per-record size ≤ 1 MB. Numbers outside the int64 and decimal ranges are rejected.
- **CSV:** field-size limit, encoding detection with BOM handling, quote-balance errors reported by row.
- **Mapping profiles and settings:** `yaml.safe_load` only, then Pydantic validation. There is no code execution in profiles (transforms are an allowlisted set of named functions).
- **Watchlist imports:** format-validated. Categories are from the enum. Confidence is in (0, 1].

## 13.4 Output handling

- **CSV/XLSX formula injection (I16):** cells beginning with `=`, `+`, `-`, `@`, tab or CR are prefixed with `'`.
- **Reports:** Jinja2 autoescape on for HTML, then WeasyPrint. Templates are part of the image and never user-supplied.
- **Notes:** Markdown rendered with a sanitiser (no raw HTML).
- **Graph labels:** rendered as text by Cytoscape, Sigma and deck.gl, never as HTML.
- **Headers:** CSP plus the security headers from Caddy and Vercel (§12.5.2, §12.6.1). The API sets `Cache-Control: no-store` on authenticated responses.

## 13.5 Supply chain

- `uv.lock` (with hashes) and `pnpm-lock.yaml` (integrity) are committed. Base images are **pinned by digest**.
- An **SBOM** (syft, SPDX) and a **vulnerability scan** (grype, fail on critical) run for every image and every release.
- **Licence check** in CI: every dependency must be permissive or compatible. The data licences are honoured in-product:
  - DB-IP Lite **CC BY 4.0**: attribution shown on the IP enrichment panel and the About page;
  - IBM Plex **SIL OFL**;
  - Natural Earth **public domain**;
  - Tor exit lists from the Tor Project;
  - X4BNet lists under their repository licence (attribution in About).
- Renovate or Dependabot opens weekly update PRs. Each goes through the full CI including the evaluation gate.
- **Air-gapped install fetches nothing.** Every byte is inside the verified bundle. Optional `cosign` signing uses a team key kept offline.

## 13.6 Data handling and privacy

- **Synthetic only** in the repository, CI and the showroom. Real traffic data never enters git. A pre-commit hook blocks large data files outside `samples/`.
- **Retention:**
  - demo uploads: 60 minutes;
  - runs: last 5 per dataset unless referenced by a case;
  - audit: forever;
  - access logs: rotated at 90 days `[DEFAULT]`.
- **Encryption at rest** is delegated to the host: full-disk encryption (LUKS) is recommended in the air-gap README. Backups can be encrypted with `age` (§12.11).
- **Logs** carry identifiers, never raw rows or secrets.

## 13.7 Lawful and ethical use

These positions are printed in the model cards, the README and the write-up, because they are part of the product:

1. **Leads, not verdicts.** Every output is a hedged, confidence-scored hypothesis with its evidence (I17). CIOH clusters are labelled *heuristic* everywhere.
2. **Human in the loop** for consequential steps: merges below 0.9, escalations, and exports of escalated cases.
3. **Oversight built in:** the Auditor role, the hash-chained audit, the access log, and independent verification of evidence packs.
4. **No geographic profiling.** `[DECISION]` No country or ASN *identity* enters `lead_ranker`. Only infrastructure *type* (Tor, VPN, hosting) and *diversity* counts do.
   - A user is never scored as riskier *because of where they are*.
   - `test_country_ablation_stability` checks that dropping all geo features changes the top-50 by less than 10%.
5. **Victims are protected.** Victim-like actors are excluded from suspect lists (E14).
6. **Out-of-scope uses** (model cards):
   - automated sanctioning;
   - identifying individuals without lawful process;
   - any use on data not lawfully obtained.
7. **Built and demonstrated on synthetic data only.** The PS itself stipulates that no real seized or intercepted data is provided.

## 13.8 OWASP API Security Top 10, read against this application

| Risk | Where it could bite us | Control |
|---|---|---|
| Broken object-level auth | Case and export IDs | Ownership and role checks in the service layer. ULIDs are not the security boundary. `test_cannot_read_others_export` |
| Broken authentication | Refresh flow | Rotation plus reuse detection |
| Broken object-property-level auth | PATCH on leads and users | Pydantic input models with explicit allowlisted fields |
| Unrestricted resource consumption | Uploads, graph queries | Caps, `limit ≤ 500`, path search `max_hops ≤ 8`, subgraph ≤ 150 nodes, timeouts |
| Broken function-level auth | Admin routes | `require()` everywhere, tested as a matrix |
| Sensitive business flows | Demo login | Rate limits, TTL, synthetic-only |
| SSRF | – | No server-side fetch of user URLs exists. The offline guard blocks outbound connections anyway. |
| Security misconfiguration | Swagger CDN, debug mode | Self-hosted Swagger assets. `APP_MODE` controls debug (off outside dev). |
| Improper inventory | Old API versions | A single `/api/v1`, OpenAPI diff in CI |
| Unsafe consumption of APIs | – | We consume none at runtime |

---


# PART 14 — TESTING & QUALITY

## 14.1 The test pyramid, weighted for this system

| Layer | What | Tooling | Share of effort |
|---|---|---|---|
| Unit | Parsers, validators, heuristics, feature functions, formulas (priority, grade), digests, templates | pytest | 30% |
| **Property-based** | Format round-trips, unit conversions, union-find invariants, taint conservation, digest stability | Hypothesis | 10% |
| **Golden worlds** | Hand-built mini-worlds with exact expected outputs (a 7-hop peel chain, a 5×5 Whirlpool-like mix, a NAT'd operator, a victim) plus `tiny` | pytest + generator | 20% |
| Model/eval | Target thresholds on cached val worlds, baseline comparisons, calibration | sutradhar_evals | 15% |
| API | Every route: auth, RBAC matrix, validation, pagination, problem+json | FastAPI TestClient | 10% |
| End to end | Analyst journey, export → verify, offline request audit, snapshot fallback | Playwright | 10% |
| Non-functional | Offline, security payloads, determinism, performance, load | Docker `--network none`, k6/Locust, `scripts/bench.py` | 5% |

## 14.2 The tests that are non-negotiable

Each is referenced from `docs/requirements.csv`. **A requirement is not done until its test is green on `main`.**

**OFFLINE & INTEGRITY**
- `test_offline_guard_blocks_public` · `test_offline_pipeline_no_network` · `test_web_makes_no_external_requests` (I1, I11)
- `test_run_is_deterministic` (I4) · `test_completed_run_is_read_only` (I3) · `test_training_is_deterministic`
- `test_audit_chain_verifies` · `test_audit_tamper_detected` · `test_audit_append_only_trigger` · `test_app_role_cannot_update_audit` (I5)
- `test_every_mutation_emits_audit` (I13) · `test_engine_cannot_import_truth` · `test_import_contract` (I7, I18)

**GENERATOR**
- `test_generator_deterministic` · `test_generator_exports_minimum_fields` · `test_addresses_valid_format` · `test_truth_schema` · `test_hero_story_present`
- `test_utxo_conservation` · `test_no_double_spend` · `test_change_same_script_default` · `test_exchange_sweeps_link_deposits` · `test_coinjoin_shapes_match_spec` · `test_ops_truth_complete`
- `test_propagation_reaches_all_connected` · `test_nat_clients_share_ip` · `test_observation_models_signatures` · `test_skew_truth_recorded`

**INGEST**
- `test_three_formats_same_digest` · `test_variants_same_digest` · `test_contract_fields_parsed` · `test_fee_computed_when_missing` · `test_script_type_inference` · `test_amount_unit_autodetect` · `test_no_float_money` (I9) · `test_timestamps_utc_micros` (I10)
- `test_chain_only_mode` · `test_observation_model_detection` (vantage / flow / mixed / single / none)
- `test_xxe_payload_rejected` · `test_billion_laughs_rejected` · `test_zip_bomb_rejected` · `test_deep_json_rejected` (I15)
- `test_reject_report_rows_and_rules` · `test_conflicting_txid_quarantined`
- `test_contract_roundtrip` · `test_to_sats_decimal` · `test_automapper_renamed_variant` · `test_profile_hash_stable` · `test_geoip_offline_lookup` · `test_tor_exit_flag` · `test_role_inference` · `test_refdata_manifest_schema`

**ENGINE**
- `test_prevout_exact_links` · `test_addr_amount_match_recovers_truth` · `test_external_inputs_marked`
- `test_cioh_excludes_coinjoin` (I8) · `test_mega_cluster_split` · `test_cluster_ids_deterministic`
- `test_change_merge_respects_coinjoin` · `test_peel_chain_recall_5plus_hops` · `test_exchange_payout_chain_not_flagged`
- `test_skew_estimate_correlates_with_truth` · `test_sessions_split_on_gap`
- `test_origin_beats_first_spy` · `test_unobservable_detected` · `test_tor_exit_not_co_origin` · `test_session_beats_ip_under_nat`
- `test_rejected_assertion_never_merged` · `test_accepted_assertion_always_merged`
- `test_taint_conserves_value` · `test_taint_stops_at_services` · `test_victims_not_flagged_as_perpetrators` · `test_paths_valid`
- `test_anomaly_scores_injected_outliers_high`
- `test_every_lead_has_reason_grade_calibrated_p` (I6) · `test_services_never_actor_leads` · `test_priority_formula` · `test_lead_state_carried_forward`
- `test_every_edge_has_evidence_envelope` (I2) · `test_stage_contracts` · `test_plugin_sdk_contract` · one golden test per motif detector
- `test_dims_dense_and_sorted` · `test_capability_disables_net_stages` · `test_graph_has_all_node_types` · `test_batch_payout_not_coinjoin` · `test_rule_features_on_reference_shapes` · `test_coinjoin_f1` · `test_change_precision_at_merge_threshold` · `test_embedding_deterministic` · `test_control_links_calibrated` · `test_er_improves_per_wallet_recall` · `test_exchange_detected_as_service` · `test_ppr_deterministic` · `test_tz_recovers_truth` · `test_watchlist_snapshot_frozen_per_run`

**MODELS**
- `test_models_beat_rule_baselines` · `test_calibration_ece_below_target` · `test_promotion_blocked_below_threshold` (I14) · `test_model_sha_mismatch_refuses_load` · `test_country_ablation_stability` · `test_origin_calibration_ece` · `test_retrain_uses_feedback_labels`

**EVIDENCE & EXPLANATION**
- `test_reasons_match_top_contributions` · `test_counterfactual_reduces_p` · `test_subgraph_bounded` · `test_reason_templates_are_hedged` (I17)
- `test_evidence_pack_verifies` · `test_tampered_pack_fails_verify` · `test_pack_reproduces_result_digest` · `test_csv_injection_neutralised` (I16)
- `test_misp_export_valid` · `test_graphml_roundtrip`

**API & SECURITY**
- `test_every_mutating_endpoint_declares_permission` · `test_rbac_matrix` · `test_no_unpaginated_list_endpoints` (I12)
- `test_refresh_reuse_revokes_family` · `test_login_lockout` · `test_cannot_change_own_role` · `test_cannot_read_others_export` · `test_escalated_export_requires_approval`
- `test_demo_upload_ttl_purge` (I19) · `test_enrichment_provenance_present` (I20)

**UI (Playwright)**
- `e2e_analyst_journey`: login → triage → open lead → Why → canvas → add to case → export pack → verify seal
- `e2e_ingest_mapping_wizard` (renamed-columns variant) · `e2e_lead_evidence_tabs_render` · `e2e_replay_plays` · `e2e_snapshot_fallback` (API killed) · `e2e_keyboard_triage` · `e2e_hindi_locale_smoke`
- `test_propagation_posterior_monotone_information` (Replay truthfulness) · `test_academy_answers_never_sent_to_client`

## 14.3 Performance targets and how they are measured

| Target `[DEFAULT]` | Measured by |
|---|---|
| Ingest ≥ 10 k rows/s end to end (CSV, reference laptop) | `scripts/bench.py ingest` on the hero CSV |
| Hero world upload → published ≤ 10 min (8 vCPU / 16 GB) | `bench.py e2e` in `release.yml` on a pinned runner size, and on the team's reference laptop |
| Worker peak RSS ≤ 6 GB (hero) · API RSS ≤ 1.2 GB (demo) | `bench.py` memory sampling |
| API p95: list/detail < 300 ms · neighbours < 400 ms · subgraph < 800 ms, at 20 concurrent users | k6 (or Locust) script against the demo image |
| Canvas: 60 fps pan/zoom at 2,000 elements · Sigma overview interactive at 50 k | Playwright trace + manual check on the reference laptop |
| Shell JS ≤ 350 KB gzip | `vite build` report in CI |

**Measured numbers are published** on the metrics page next to the targets. A missed target is shown as missed.

## 14.4 Standing quality rules

1. **Trunk-based.** Short-lived branches, squash merges, **Conventional Commits** (`feat(engine): E10 origin pass-2 consistency features [R-PS-03]`).
2. **Every PR:**
   - cites its requirement IDs;
   - adds or updates tests;
   - updates docs if it changes behaviour;
   - includes a screenshot or GIF for UI;
   - adds no external URL (CI enforces);
   - has reversible migrations.
3. **Reviews:** one approval; **two** for changes in `engine/stages`, `models/` or `audit`.
4. **Definition of done (feature):** requirement ID linked · tests green · offline-safe · audited if mutating · documented · **demoable in under a minute**.
5. **An ADR for every decision a future teammate might reverse** (`docs/adr/`). Start with D1–D24 (§16.3).
6. **Rules for AI coding agents** (pasted into every session with §17.15):
   - load `docs/INVARIANTS.md` first;
   - never add a network call;
   - never import `sutradhar_evals` or truth from the engine;
   - money is integer satoshis;
   - time is UTC microseconds;
   - every new edge carries an envelope;
   - every mutation is audited;
   - write the test first for any stage change.
7. **Demo every Sunday.** Each sprint ends with a 2-minute recorded demo of what changed, posted in the team channel. It is also the rehearsal for the finale.

---


# PART 15 — THE BUILD PLAN

> Six people, ten weeks, one deadline we don't control yet (the finale date, `[OPEN-04]`). The plan is built around three principles:
> 1. **Always deployable.** A thin end-to-end slice is live on day 11, and every change after that ships to the showroom automatically.
> 2. **Risk first.** The generator and the correlation engine are the unknowns, so they start in week 1, not week 6.
> 3. **Every phase ends in something demoable**, recorded on Sunday.

## 15.1 Team roles

Names are `[OPEN-02]`. Assign one person per role on day 1. The team lead also owns the pitch.

| Role | Owns | Packages |
|---|---|---|
| **M1 · Platform** | API, auth, audit, job queue and SSE, DB and migrations, watchlists/cases/exports APIs, CI/CD, Render and Vercel deploys, air-gap bundle, security pass, performance infrastructure, retrain plumbing | `apps/api`, `deploy/`, `.github/` |
| **M2 · World & Evals** | Generator, scenario packs, adversary knobs, truth, **evaluation harness**, metrics JSON, red-team, sensor planner, Academy content and scoring | `packages/generator`, `packages/evals` |
| **M3 · Data & On-chain** | Ingestion (I01–I06), enrichment, reference data consumption, flows, `coinjoin_clf`, clustering, `change_clf`, `peel_scorer`, motifs and plugin SDK, services and victims, embeddings, interop exports | `packages/engine` (ingest, E01–E08, E12, E14), `packages/plugins` |
| **M4 · Network & Ranking ML** | Timing, `origin_ranker`, control and co-origin, entity resolution, timezone fingerprint, taint/PPR/paths, anomaly, `lead_ranker`, calibration, explanations, drift, training pipeline, model cards | `packages/engine` (E09–E11, E13, E15–E18), `models/` |
| **M5 · Product UI** | Design system, shell, ingest UI, triage, lead detail, dossiers, cases/evidence/verify UI, Govern UI, Lab UIs (Studio, Academy), i18n and accessibility | `apps/web` (all but canvas, replay, geo), `packages/tokens` |
| **M6 · Visualisation, site & story** | Investigate canvas, **Replay**, geo map, Sankey, overview charts, landing/docs/**metrics site**, demo video, deck, pitch | `apps/web/features/{investigate,replay,geo,flows}`, `apps/site` |

**Pairing rule.** The **critical path** (below) always has two people who can work on it. M3 and M4 review each other's engine code. M5 and M6 review each other's UI.

## 15.2 Calendar

Sprints run Monday to Sunday. Sprint 0 is the short first week.

| Sprint | Dates | External milestones |
|---|---|---|
| **S0** | Thu 1 Oct – Sun 4 Oct | Roles, accounts, repo (§16.1) |
| **S1** | 5 – 11 Oct | **Walking skeleton live (Sun 11 Oct)** |
| **S2** | 12 – 18 Oct | |
| **S3** | 19 – 25 Oct | Generator v1.0 frozen (Sun 25 Oct) |
| **S4** | 26 Oct – 1 Nov | Targets review #1 |
| **S5** | 2 – 8 Nov | **SIH results expected (first week of Nov)** · Targets review #2 (freeze) |
| **S6** | 9 – 15 Nov | **Mentoring window opens (~10 Nov)** |
| **S7** | 16 – 22 Nov | |
| **S8** | 23 – 29 Nov | |
| **S9** | 30 Nov – 6 Dec | **Feature freeze Sun 6 Dec** `[DEFAULT]` |
| **F** | 7 Dec → finale | Rehearsals. Finale date `[OPEN-04]`. |

```
              S0   S1   S2   S3   S4   S5   S6   S7   S8   S9   F
 P0 Found.    ███  ███
 P1 World          ███  ███  ███
 P2 Ingest         ███  ███  ███
 P3 On-chain            ███  ███  ███
 P4 Network                  ███  ███  ███
 P5 Ranking                       ███  ███  ███
 P6 UI             ███  ███  ███  ███  ███  ███  ███
 P7 Signature                          ███  ███  ███  ███
 P8 Harden                                       ███  ███  ███
 P9 Finale                                                  ███  ███
```

**Critical path:** data contract (P0.2) → generator v0 (P0.3) → ingestion (P2) → flows, CoinJoin and clustering (P3.1–P3.3) → origin attribution (P4.2–P4.3) → lead ranker (P5.5) → lead detail (P6.3) → Replay (P7.1) → air-gap bundle (P8.3). **Anything on this path that slips by more than two days triggers the scope-cut order (§15.13).**

## 15.3 Who does what, sprint by sprint

| | M1 Platform | M2 World & Evals | M3 Data & On-chain | M4 Network & Ranking | M5 Product UI | M6 Viz & Story |
|---|---|---|---|---|---|---|
| **S0** | P0.1 repo/CI · P2.7 refdata fetch | P0.3 generator v0 | P0.2 data contract | P0.2 contract · training design | P0.6 design system start | Brand, tokens, site placeholder |
| **S1** | P0.5 API · P0.7 deploy · P0.8 offline | P1.1 economy | P0.4 engine skeleton · P2.1 readers | P0.4 support · P3.8 training pipeline v0 | P0.6 shell · P6.1 | P0.7 Vercel · canvas prototype |
| **S2** | P2.8 ingest API · jobs/SSE hardening | P1.2 agents · P1.3 CoinJoin coordinators | P2.2 mapping · P2.3 normalise · P2.4 validate | P1.5 propagation (with M2) · P4.1 timing | P2.8 ingest UI | P6.4 canvas |
| **S3** | Cases/exports API skeleton · audit endpoints | P1.4 ops · P1.5 network · P1.6 observation | P2.5 X-ray · P2.6 enrichment · P3.1 flows | P4.2 origin features + baselines | P6.2 triage | P6.4 canvas · path finder |
| **S4** | P5.1 watchlists API · P5.8 publish/diff | P1.7 exporters · P1.8 packs → **gen v1.0** · P3.9 eval v1 | P3.2 CoinJoin · P3.3 clustering · P3.4 change | P4.3 origin_ranker · P4.4 control | P6.3 lead detail | Metrics page v0 · P6.4 |
| **S5** | P7.3 retrain plumbing · P8.5 demo hardening start | P7.2 adversary sweeps · eval v2 | P3.5 peel · P3.6 motifs/SDK · P3.7 embeddings | P4.5 ER · P4.6 fingerprints · P4.7 eval | P6.5 dossiers · P6.7 cases | **P7.1 Replay** |
| **S6** | P8.1 security pass | P7.5 Studio backend · P7.6 Academy scoring | P5.2 services/victims · P7.7 interop | P5.3 risk · P5.4 anomaly · P5.5 ranker | P6.7 exports/verify UI · ER suggestions UI | P7.1 Replay · P6.6 geo |
| **S7** | P8.3 bundle · P8.2 perf infra | P7.6 Academy · red-team page | P8.2 engine perf · schema drills | P5.6 leads · P5.7 explain · P7.4 cards | P6.8 Govern · P7.5 Studio UI | P6.6 Sankey · docs site |
| **S8** | P8.4 offline suite · P8.7 restore drill | P7.8 planner `[STRETCH]` | Bug fixes · surprise-schema drills | P7.3 feedback loop · P7.9/7.10 `[STRETCH]` | P6.9 i18n · a11y · states | P8.6 docs · video script |
| **S9** | **P8.8 release v1.0.0** | Final eval report | Freeze fixes | Final model promotion | Freeze fixes | Deck · video |
| **F** | Contingency kit | Judge challenge | Drills | Q&A drills | Dry runs | Pitch |

---

## P0 — Foundations & the walking skeleton · S0–S1 (1–11 Oct) · everyone

> **Goal.** By Sunday 11 October, a **public URL and an offline compose stack** both show one stub lead produced end to end from a generated CSV, and CI is green. Every later phase deepens a pipeline that already runs.

### P0.1 — Repository, workspaces, tooling · M1 · 2 d
- **Build:**
  - monorepo per §12.1;
  - the root `pyproject.toml` with `[tool.uv.workspace] members = ["apps/api", "packages/*"]`;
  - `pnpm-workspace.yaml` (`apps/*`, `packages/*`);
  - `ruff.toml`, `pyrightconfig.json`, `.importlinter` (contract per §3.3), `.pre-commit-config.yaml` (ruff, eslint, prettier, large-file guard);
  - a `Makefile` (`dev`, `lint`, `fmt`, `test`, `e2e`, `bench`, `bundle`, `demo-data`);
  - `docs/INVARIANTS.md` (copied from §3.6);
  - `docs/adr/0001-offline-first.md` through `0006-*` (from D1–D6).
- **Repo:** private at first (§16.3 D21). Branch protection on `main` (PR + green CI).
- **Packaging:** distribution names `sutradhar-<pkg>`, import names `sutradhar_<pkg>`. The CLI entry point is `sutradhar = "sutradhar_cli.main:app"`.
- **CI:** `ci.yml` with `py` and `js` jobs, caching uv and pnpm.
- **Tests:** `test_import_contract` passes on empty packages.
- **Done when:** a fresh clone runs `make lint test` green locally and in CI in under 5 minutes.

### P0.2 — Data contract v1 and shared schemas · M3 + M4 · 2 d
- **Build `packages/schemas/sutradhar_schemas/`:**
  - `contract.py`: `CanonicalRecord` (§4.2), `Sats = Annotated[int, Ge(0)]`, `TsUs = int`, and a `to_sats(value, unit) -> int` that goes through `Decimal`;
  - `profile.py`: `MappingProfile` (§4.3.2);
  - `envelope.py`: `EvidenceEnvelope`;
  - `lead.py`: `LeadSummary`, `Reason`, `Family`, `Grade`, `LeadType`;
  - `manifest.py`: `RunManifest`;
  - `sutradhar schemas export` → JSON Schemas → generated `docs/data-contract.md`.
- **Engine DDL v0:** `packages/engine/sutradhar_engine/store/ddl.sql` (`obs`, `tx`, `txin`, `txout`, `d_*`, `run_meta`).
- **Tests:** `test_contract_roundtrip`, `test_to_sats_decimal` (Hypothesis over BTC strings and floats' string forms), `test_no_float_money`.
- **Done when:** contract v1 is tagged. **Any later change needs an ADR** (the generator, engine and UI all depend on it).

### P0.3 — Generator v0 ("tiny") · M2 · 3 d
- **Build:**
  - `sutradhar_gen/world.py`: `SeedSequence` tree, event heap, block clock;
  - `addresses.py`: base58check, bech32 and bech32m encoders following the BIP-173/350 reference code, with checksum-verified output;
  - a minimal economy: 100 users and 1 exchange with deposit/sweep;
  - one ransomware op: 4 victims → consolidation → a 5-hop peel;
  - network v0: 200 nodes, 5 sensors, exponential delays, Dijkstra;
  - vantage observation;
  - canonical CSV exporter;
  - truth files (`agents`, `addresses`, `txs`, `origins`);
  - CLI `sutradhar gen run --scenario tiny --seed 1`.
- **Tests:** `test_generator_deterministic` (byte-identical outputs for the same seed), `test_generator_exports_minimum_fields`, `test_addresses_valid_format`.
- **Done when:** `tiny` generates in under 10 s with a complete truth set.

### P0.4 — Engine skeleton · M3 (+M4) · 3 d
- **Build:**
  - `ingest/` with I01 (CSV only), I02 (identity profile), I03 (normalise), I05 (dedupe) and I06 (minimal X-ray) → `dataset.duckdb`;
  - stages `e01_load.py` and `e19_publish.py` (table digests, result digest, manifest);
  - a **stub** `e17_rank.py` that emits one TX lead per peel-shaped transaction, with one hedged reason, so the pipeline is end to end;
  - `RunContext`, `StageReport` and the stage runner with resume;
  - CLI `sutradhar ingest <files> --profile identity` and `sutradhar run <dataset>`.
- **Tests:** `test_stage_contracts` (scaffold), `test_run_is_deterministic` on `tiny`.
- **Done when:** CLI ingest plus run produces `run.duckdb`, ≥ 1 lead and a manifest, twice, with the same digest.

### P0.5 — API skeleton · M1 · 4 d
- **Build `apps/api/sutradhar_api/`:**
  - app factory, `pydantic-settings` config (`APP_MODE`…);
  - SQLAlchemy models for `users`, `sessions`, `datasets`, `dataset_files`, `runs`, `jobs`, `job_events`, `leads`, `lead_state`, `audit_log`, `audit_head` and `settings`;
  - **Alembic `0001`** generating Postgres DDL and SQLite DDL (the audit triggers per dialect);
  - auth: login, refresh (rotation and reuse detection), logout, demo; argon2id; PyJWT;
  - `require()` plus the permission matrix;
  - `audit.append()` and `audit.verify()` (§8.6);
  - **job queue:** a `jobs` table and `worker.run_forever(concurrency)`:
    - Postgres claims with `SELECT … FOR UPDATE SKIP LOCKED`;
    - SQLite uses a single embedded worker thread;
    - each job runs in a `multiprocessing` **spawn** subprocess with a heartbeat;
  - SSE endpoint (`sse-starlette`) streaming `job_events`;
  - routes: health, ready, system/info, datasets (upload), runs (create/list/get), leads (list/get);
  - `offline_guard.install()`;
  - self-hosted Swagger assets.
- **Tests:** `test_audit_chain_verifies`, `test_audit_append_only_trigger` (Postgres and SQLite), `test_offline_guard_blocks_public`, `test_no_unpaginated_list_endpoints`, `test_every_mutating_endpoint_declares_permission`.
- **Done when:** upload → job → run → leads through the API, with live SSE progress.

### P0.6 — Web shell · M5 (+M6 for tokens) · 4 d
- **Build `apps/web`:**
  - Vite + React 19 + TypeScript strict;
  - Tailwind v4 and a shadcn init (button, input, table, tabs, dialog, sheet, command, badge, tooltip);
  - `@sutradhar/tokens`; IBM Plex via Fontsource;
  - TanStack Router routes (`/login`, `/`, `/triage`, `/leads/$id`, `/govern/system`);
  - `@sutradhar/client` generated from OpenAPI;
  - auth (login, refresh, demo button);
  - run selector (`?run=`), mode badge;
  - basic triage table; lead detail (Summary and Why);
  - `useSSE()` hook;
  - `scripts/check-no-external-urls.mjs`.
- **Tests:** Vitest for formatters (sats → BTC, IST); a Playwright smoke test (login → triage → lead).
- **Done when:** the UI shows the stub lead from the API, locally.

### P0.7 — Deploy skeleton · M1 + M6 · 2 d
- **Build:**
  - `api.Dockerfile`, `web.Dockerfile`, `demo.Dockerfile`;
  - `images.yml` pushing to GHCR;
  - Render service (image-backed, **Standard**, Singapore), registry credential, **deploy hook**;
  - `deploy.yml` (hook with `imgURL`);
  - Vercel projects `sutradhar-web` (`apps/web`) and `sutradhar-site` (`apps/site` placeholder with links);
  - CORS env; UptimeRobot monitor.
- **Done when:** `https://<web>.vercel.app` shows the stub lead served from `https://<api>.onrender.com`, and the README carries both links and a CI badge.

### P0.8 — Offline skeleton · M1 · 2 d
- **Build:**
  - `compose.dev.yaml` and `compose.airgap.yaml` (§12.5.1, internal network, two DB roles);
  - `Caddyfile`;
  - `sutradhar selftest --scenario tiny` (generate → ingest → run → verify the audit chain);
  - CI job `offline-engine` (`docker run --network none`);
  - `compose.offline-test.yaml` plus a Playwright container asserting that no request leaves the app host.
- **Done when:** CI proves I1 and I11 on the skeleton.

**P0 exit:** public URL live · offline stack live · CI green (lint, types, unit, offline engine, offline e2e) · Sunday demo recorded · the §16.1 accounts and decisions resolved.

---

## P1 — The synthetic world · S1–S3 (5–25 Oct) · M2 (+M4 on propagation)

> **Goal.** Generator v1.0 is frozen on 25 October: hero, stress packs and 40/10/10 randomised worlds, all cached. Models depend on it, so any change after the freeze needs an ADR and a re-run of the evaluation.

### P1.1 — Economy and wallets · 4 d
- **Build `economy/`:**
  - `Wallet` (UTXO set, address policy, fingerprint);
  - coin selection: `largest_first`, `random_improve`, `single_random_draw`;
  - change creation with a dust rule;
  - fee model (log-normal with a daily congestion curve);
  - vsize estimator (§5.2 weights);
  - script mix and address reuse.
- **Tests:** `test_utxo_conservation` (Σin = Σout + fee for every tx), `test_no_double_spend`, `test_change_same_script_default`.

### P1.2 — Benign agents · 3 d
- **Build `agents/`:** user, merchant, exchange (deposit addresses, **sweeps**, **batched withdrawals**, hot/cold), pool (coinbase and payout batches), gambling, payroll. Diurnal activity by country timezone.
- **Tests:** `test_exchange_sweeps_link_deposits`, a realism check on the in/out count distribution.

### P1.3 — CoinJoin coordinators · 2 d
- **Build:** Whirlpool-like (Tx0 plus 5×5 rounds at the four pool sizes, remixes), Wasabi-like (≥ 50 inputs, ≈ 0.1 BTC equal outputs, or multi-denomination), JoinMarket-like (2–10 makers plus a taker). Mostly benign participants.
- **Tests:** `test_coinjoin_shapes_match_spec`.

### P1.4 — Illicit operations · 4 d
- **Build `ops/`:**
  - ransomware (victims → consolidation → peel → cash-out → CoinJoin → post-mix mistake; W2 infrastructure wallet);
  - darknet market;
  - scam;
  - the seven laundering typologies;
  - mules;
  - **victims explicitly labelled**.
- **Tests:** `test_ops_truth_complete`, one shape test per typology.

### P1.5 — P2P network and propagation · 4 d · M2 + M4
- **Build `net/`:**
  - topology: listeners, clients, NAT/CGNAT sharing, Tor exits from the snapshot, VPN ranges;
  - `ipspace.py`: samples IPs *inside real DB-IP ranges* by ASN category (needs P2.7 refdata);
  - sessions (log-normal lifetimes);
  - `propagate.py`: fresh exponential delays per tx, 2 s / 5 s outbound/inbound means `[DEFAULT]`, latency, SciPy Dijkstra, `multiprocessing` over tx batches;
  - re-broadcast.
- **Tests:** `test_propagation_reaches_all_connected`, `test_nat_clients_share_ip`, a propagation-speed realism check.

### P1.6 — Observation models · 2 d
- **Build `observe.py`:** vantage, flow, mixed and single; skew, jitter, loss and duplicates; sensor truth.
- **Tests:** `test_observation_models_signatures` (the X-ray from P2.5 detects each), `test_skew_truth_recorded`.

### P1.7 — Truth, exporters and variants · 3 d · M2 + M3
- **Build:** truth writers (§5.8), canonical exporters (CSV, JSON, NDJSON, XML), every §5.9 variant, the partial watchlist.
- **Tests:** `test_truth_schema`, and `test_variants_same_digest` (activated once P2 lands).

### P1.8 — Scenario packs, randomisation, realism, CLI · 3 d
- **Build:**
  - `scenarios/*.yaml` (tiny, **hero-ghostline**, bazaar, benign-heavy, tor-heavy, onion-only, sparse-sensors, nat-crowded, coinjoin-heavy, flow-isp, schema-zoo, academy-01…05);
  - `gen randomize` (§5.11 ranges);
  - `gen validate` (§5.12 report);
  - `arrivals.npz` sampling;
  - a CI cache keyed by generator version and seed.
- **Tests:** `test_hero_story_present` (the GHOSTLINE structure exists exactly as specified in truth). Performance: hero ≤ 10 min.

**P1 exit:** generator **v1.0** tagged · every pack generated and cached · realism report reviewed by two teammates · story walkthrough of `hero-ghostline` recorded.

---

## P2 — Ingestion & enrichment · S1–S3 (5–25 Oct) · M3 (+M1, M5)

> **Goal.** Any sensible file becomes a validated, normalised, profiled dataset: CSV, JSON and XML, renamed columns, BTC or sats. Proven by digests, not by eye.

### P2.1 — Streaming readers · 3 d
- **Build `ingest/readers/`:**
  - `csv.py` (Polars batched reader, delimiter/BOM/encoding handling);
  - `json_array.py` (`ijson` items);
  - `ndjson.py` (Polars);
  - `xml.py` (`defusedxml` + `lxml.iterparse`, `record_xpath`, both nesting styles);
  - `compressed.py` (gzip, zstd, ratio guard);
  - guards for V20.
- **Tests:** a format matrix, plus `test_xxe_payload_rejected`, `test_billion_laughs_rejected`, `test_zip_bomb_rejected`, `test_deep_json_rejected`.

### P2.2 — Mapping profiles and the auto-mapper · 3 d
- **Build:**
  - `profile.apply()`;
  - `automap.py`: a synonym table plus value-shape detectors (64-hex, IPs, ports with an 8333 share, address charsets, timestamps, amount magnitudes), giving per-field confidence;
  - built-in profiles for every generator variant.
- **Tests:** `test_automapper_renamed_variant` (≥ 0.9 confidence on all required fields), `test_profile_hash_stable`.

### P2.3 — Normalisation · 3 d
- **Build:**
  - sats via `Decimal`, and **amount-unit auto-detection** (§4.2);
  - time parsing: ISO with/without offset, epoch s/ms/µs by magnitude, → UTC µs;
  - array decoding: JSON, delimited, indexed;
  - canonical IPs, lowercase txids;
  - script-type inference (§4.3.3).
- **Tests:** Hypothesis properties for conversions; `test_amount_unit_autodetect`, `test_timestamps_utc_micros`, `test_script_type_inference`.

### P2.4 — Validation and rejects · 2 d
- **Build:** V01–V20 as vectorised Polars expressions; a `rejects` writer; CSV download (neutralised).
- **Tests:** one test per rule; `test_reject_report_rows_and_rules`, `test_csv_injection_neutralised`.

### P2.5 — Reconcile, capability profile, X-ray · 2 d
- **Build:** exact dedupe (V11), content-hash conflict quarantine (V10), `capability.py` (§4.5, observation-model detection), `xray.json`.
- **Tests:** `test_observation_model_detection` (all five), `test_conflicting_txid_quarantined`, `test_chain_only_mode`.

### P2.6 — Enrichment (E02) · 3 d
- **Build:**
  - `refdata.py` (memory-mapped `maxminddb` readers; Tor exact set; VPN and datacenter CIDR interval sets with bisect over integer ranges; bogon table);
  - `e02_enrich.py` (lookups, role inference, sensor detection, provenance per value).
- **Tests:** `test_geoip_offline_lookup`, `test_tor_exit_flag`, `test_role_inference`, `test_enrichment_provenance_present`.

### P2.7 — Reference-data pipeline · 1 d · M1 (S0, early, because the generator needs it)
- **Build `scripts/fetch-refdata.sh`:**
  - DB-IP `dbip-country-lite` and `dbip-asn-lite` (**mmdb** for lookups **and CSV** for the generator's IP ranges) from `https://download.db-ip.com/free/dbip-{country,asn}-lite-YYYY-MM.{mmdb,csv}.gz`;
  - Tor `https://check.torproject.org/torbulkexitlist`;
  - X4BNet `output/vpn/ipv4.txt` and `output/datacenter/ipv4.txt`.

  Output goes to `refdata/snapshots/<source>/<as_of>/`, and `refdata/manifest.json` records the SHA-256, licence and source URL. `nightly.yml` opens a PR when anything changes.
- **Tests:** `test_refdata_manifest_schema`, and the enrichment tests use the pinned snapshot.

### P2.8 — Ingest API and UI · 4 d · M1 + M5
- **API:** multipart streaming upload (server-generated paths), `POST /datasets/{id}/mapping`, `GET …/xray`, `GET …/rejects`, the profile CRUD.
- **UI:** dropzone → mapping wizard (confidence chips, 20-row normalised preview, save profile) → I01–I06 progress stepper (SSE) → X-ray screen → "Run analysis".
- **Tests:** `e2e_ingest_mapping_wizard` on the `renamed` variant.

**P2 exit:** `test_three_formats_same_digest` and `test_variants_same_digest` green · hero CSV ingests in ≤ 3 min · X-ray screen live on the showroom.

---

## P3 — On-chain intelligence · S2–S4 (12 Oct – 1 Nov) · M3 (+M4, M2, M6)

> **Goal.** The ledger side is complete: flows, CoinJoin scoring, safe clustering, change, peel chains, motifs and embeddings. It is measured on held-out worlds against rule baselines, and the metrics page is live.

### P3.1 — E03 flows · 3 d · M3
- **Build `e03_flows.py`:**
  - the prevout path;
  - **(address, amount) matching**: a DuckDB join on `(address, sats)` with `created_us < spent_us`, ranked; greedy one-to-one assignment in spend-time order; Python resolves only groups with multiple candidates; confidence = 1/k;
  - external-funding flags;
  - `utxo_spend`.
- **Tests:** `test_prevout_exact_links`, `test_addr_amount_match_recovers_truth` (≥ 0.99), `test_external_inputs_marked`.

### P3.2 — E04 CoinJoin features, rules and `coinjoin_clf` · 3 d · M3
- **Build:** `features/coinjoin.py` (§6.5), `rules/coinjoin_rules.py` (published heuristics as booleans), a training entry point in `evals/train.py` (labels from truth, with `batch_payout` as a class), model artefact v1.0.0 plus a card stub, and `e04_coinjoin.py`.
- **Tests:** `test_batch_payout_not_coinjoin`, `test_rule_features_on_reference_shapes`, and `test_coinjoin_f1` against target.

### P3.3 — E05 clustering with the CoinJoin guard · 2 d · M3
- **Build `e05_cluster.py`:**
  - star edges from eligible transactions;
  - `scipy.sparse.csgraph.connected_components`;
  - deterministic relabelling;
  - mega-cluster inspection and split.
- **Tests:** `test_cioh_excludes_coinjoin` (I8), `test_cluster_ids_deterministic`, `test_mega_cluster_split`.

### P3.4 — E06 change and `change_clf` · 3 d · M3
- **Build:** output features (§6.7), `change_clf` v1, and a merge policy at p ≥ 0.95.
- **Tests:** `test_change_precision_at_merge_threshold`, `test_change_merge_respects_coinjoin`.

### P3.5 — E07 peel chains and `peel_scorer` · 3 d · M3
- **Build:** traversal over `utxo_spend` (§6.8), chain features, `peel_scorer` with isotonic calibration (negatives include exchange payout sequences), CHAIN lead candidates.
- **Tests:** `test_peel_chain_recall_5plus_hops`, `test_exchange_payout_chain_not_flagged`.

### P3.6 — E08 motifs as plugins, plus SDK v1 · 3 d · M3
- **Build:**
  - `sdk.py` (the `Detector` protocol, `MotifHit`, params via Pydantic);
  - entry-point discovery plus an admin plugin directory;
  - built-ins in `packages/plugins`: `fan_in`, `fan_out`, `scatter_gather`, `gather_scatter`, `cycle`, `stack`, `pass_through`;
  - windowed entity-flow aggregation.
- **Tests:** one golden mini-world per detector, `test_plugin_sdk_contract`.

### P3.7 — E12 embeddings · 2 d · M3
- **Build `e12_embed.py`:** entity flow graph → normalised adjacency → `randomized_svd(k = 32)` → L2 normalisation.
- **Tests:** `test_embedding_deterministic`; the evaluation reports kNN same-owner precision@10.

### P3.8 — Training pipeline v1 · 3 d · M4 (started S1)
- **Build `sutradhar train`** (the `evals/train.py` orchestration):
  - run engine stages up to a model's input on each training world;
  - join truth labels;
  - LightGBM with the determinism flags and early stopping on `val-rand`;
  - isotonic calibration;
  - write the artefact directory (§7.5), including `reference_hist.json` and `metrics.json`.
- **Tests:** `test_training_is_deterministic`, `test_model_sha_mismatch_refuses_load`.

### P3.9 — Evaluation harness v1 and metrics page v0 · 3 d · M2 + M6
- **Build:**
  - `evals/metrics.py` (every §11.1 metric available so far, including per-wallet P/R per Müller et al.);
  - `evals/report.py` (JSON with bootstrap CIs over worlds);
  - `eval.yml`;
  - the site `metrics` page rendering `latest.json`.
- **Done when:** the metrics page shows CoinJoin F1, CIOH per-wallet P/R, change precision@0.95 and chain recall, each against its baseline.

**P3 exit:** on-chain metrics published · **targets review #1** (recorded in the decision log) · the canvas can render entities and chains from real run output.

---

## P4 — Network correlation · S3–S5 (19 Oct – 8 Nov) · M4 (+M3, M5, M2)

> **Goal.** The centrepiece works and is measured. Origin attribution beats first-spy on worlds it never saw, control and co-origin link wallets across on-chain gaps, and entity resolution raises per-wallet recall without costing precision.

### P4.1 — E09 timing · 2 d
- **Build `e09_timing.py`:** per-sensor skew estimation (robust medians, bootstrap CI, apply only if significant), within-sensor ranks, session building (ephemeral ports, 30-minute gaps), the listener-session flag.
- **Tests:** `test_skew_estimate_correlates_with_truth`, `test_sessions_split_on_gap`.

### P4.2 — E10 features and baselines · 3 d
- **Build `features/origin.py`:** every §6.11 feature group, vectorised in DuckDB and Polars, plus the **first-spy** and **first-sender** baselines as first-class estimators with the same output schema.
- **Tests:** feature-parity tests (the vantage, flow and mixed code paths agree on shared features).

### P4.3 — `origin_ranker`: training, abstention, calibration · 4 d
- **Build:**
  - `pair_booster` (binary, softmax-decoded per transaction);
  - `observable_booster`;
  - the combined decoder;
  - isotonic calibration of top-1;
  - training across `train-rand`, which randomises sensors and observation models.

  Two-pass inference is wired in `e10_origin.py`.
- **Tests:** `test_origin_beats_first_spy`, `test_origin_calibration_ece`, `test_unobservable_detected`.

### P4.4 — E11 control, crowdedness, co-origin · 3 d
- **Build `e11_control.py`:** noisy-OR aggregation at session and IP level, crowdedness and IDF, co-origin edges with the Tor/VPN/hosting exclusion.
- **Tests:** `test_control_links_calibrated`, `test_tor_exit_not_co_origin`, `test_session_beats_ip_under_nat`.

### P4.5 — E13 entity resolution, suggestions, assertions · 4 d · M4 + M5 + M1
- **Engine:** blocking (five sources, cap 200 k), pair features, `er_pair_clf`, union-find with cannot-link constraints, suggestions, application of analyst assertions.
- **API:** `merge-suggestions`, `POST /merge-decisions` (lead role, audited).
- **UI:** the suggestions panel in the actor dossier (accept/reject with reason).
- **Tests:** `test_er_improves_per_wallet_recall`, `test_rejected_assertion_never_merged`, `test_accepted_assertion_always_merged`.

### P4.6 — Behavioural fingerprints · 2 d
- **Build:** 24-bin activity histograms and offset estimation by circular cross-correlation (§6.19); fee-rate and rounding profiles; anonymising-infrastructure shares.
- **Tests:** `test_tz_recovers_truth` (within ±1 h for ≥ 80% of actors with ≥ 50 txs).

### P4.7 — Network evaluation and targets review #2 · 2 d · M4 + M2
- **Build:** attribution top-1/top-3, coverage and unobservability AUROC, **per observation model and stress pack**; ER per-wallet P/R; the lift chart vs first-spy on the metrics page.
- **Done when:** targets are frozen (decision log). Any missed target has an owner and a plan, or is explicitly accepted as a published limitation.

**P4 exit:** the headline NET numbers are published · the co-origin merge of W2 is visible in the hero run · the first **Replay** data endpoint exists (feeds P7.1).

---

## P5 — Risk, ranking & explanations · S4–S6 (26 Oct – 15 Nov) · M4 (+M3, M1, M5)

> **Goal.** The ranked, explainable lead list the PS asks for. Every lead has a calibrated confidence, a grade from independent evidence, reasons, a path, a counterfactual and a bounded evidence graph. Leads survive re-runs with their triage state.

### P5.1 — Watchlists · 2 d · M1 + M5
- **Build:** `watchlists` and `watchlist_items` APIs, CSV import (validated), UI list/import/edit (lead+), and the E01 snapshot into `seed_input` with the watchlist version recorded in the manifest.
- **Tests:** `test_watchlist_snapshot_frozen_per_run`.

### P5.2 — E14 services and victims · 2 d · M3
- **Build `e14_services.py`:** service score (§6.15) with type rules, and `exposure_out` plus `victim_like`.
- **Tests:** `test_exchange_detected_as_service`, `test_victims_not_flagged_as_perpetrators`.

### P5.3 — E15 risk: taint, PPR, paths, CASHOUT · 3 d · M4
- **Build `e15_risk.py`:**
  - forward haircut taint in time order with hop decay and the service stop (vectorised per block of transactions);
  - igraph `personalized_pagerank`;
  - k-best paths (Dijkstra on −log w, k = 3, top 500 actors);
  - CASHOUT candidates.
- **Tests:** `test_taint_conserves_value` (Hypothesis on random DAGs), `test_taint_stops_at_services`, `test_ppr_deterministic`, `test_paths_valid`.

### P5.4 — E16 anomaly · 2 d · M4
- **Build `e16_anomaly.py`:** transaction and actor features, two `IsolationForest`s, percentile scores.
- **Tests:** `test_anomaly_scores_injected_outliers_high`.

### P5.5 — E17 features, `lead_ranker`, calibrators, drift · 4 d · M4
- **Build:**
  - `features/actor.py` (~70 features, §7.3.7, including the Elliptic++-comparable ones);
  - `lead_ranker` training (`scale_pos_weight`, early stopping on PR-AUC), isotonic calibration, the CASHOUT calibrator;
  - PSI drift against `reference_hist.json`.
- **Tests:** `test_models_beat_rule_baselines` (vs taint-only), `test_calibration_ece_below_target`, `test_country_ablation_stability`.

### P5.6 — Lead generation, grades, priority, state carry-over · 2 d · M4 + M1
- **Build:**
  - all five lead types (§6.18);
  - families from TreeSHAP group sums and detector hits;
  - grade and priority (§2.5.3);
  - `lead_key`;
  - E19 carry-over (NEW, then `last_seen_run_id`, then `changed_since_review`).
- **Tests:** `test_every_lead_has_reason_grade_calibrated_p`, `test_services_never_actor_leads`, `test_priority_formula`, `test_lead_state_carried_forward`.

### P5.7 — E18 explanations · 4 d · M4 + M5
- **Build:**
  - `explain/contrib.py` (LightGBM `pred_contrib=True`, feature → family grouping);
  - `explain/templates.yaml` plus the renderer;
  - **the language-guard lint**;
  - `explain/counterfactual.py` (§8.3);
  - `explain/subgraph.py` (§8.4, ≤ 150 nodes);
  - the timezone profile.
- **UI (M5):** the Why, Counterfactual and Priority tabs.
- **Tests:** `test_reasons_match_top_contributions`, `test_counterfactual_reduces_p`, `test_subgraph_bounded`, `test_reason_templates_are_hedged`.

### P5.8 — E19 publish, diff, watchlist hits · 2 d · M1
- **Build:** invariant validation before publish, digests and manifest, read-only freeze, batch publish into `leads`, the diff against `prev_run_id`, watchlist-hit events, SSE `run.published`, audit.
- **Tests:** `test_completed_run_is_read_only`, `test_run_is_deterministic` (now on the hero world, nightly).

**P5 exit:** the hero run shows the GHOSTLINE actor with its evidence. **We report where it actually ranks. We do not tune on hero.** precision@50, PR-AUC and ECE on `test-rand` are published. I4 and I6 are green.

---

## P6 — The product surface · S1–S7 (5 Oct – 22 Nov, continuous) · M5 + M6

> **Goal.** A console an analyst would choose to use. Fast, keyboard-first, evidence one hover away, and no page that looks like a hackathon.

| Sub-phase | Owner | Sprint | Build | Done when |
|---|---|---|---|---|
| **P6.1 Design system and shell** | M5 | S1–S2 | Tokens (§10.5), dark/light, density modes; shadcn components restyled; `GradeBadge`, `FamilyChips`, `ConfidenceBar`, `ProvenanceTag`, `EnvelopePopover`, `HashChip`; shell with nav, run selector, mode badge, status bar; ⌘K skeleton | A storybook-style `/govern/system/ui` page renders every component in both themes |
| **P6.2 Triage queue** | M5 | S3 | Virtualised table, filters, saved views (URL state), preview panel, keyboard map (§10.7), bulk actions, SSE-driven "new/changed" badges | `e2e_keyboard_triage` |
| **P6.3 Lead detail** | M5 | S4–S5 | All nine tabs (§8.1), action bar, provenance popovers, "open in canvas", "replay" | `e2e_lead_evidence_tabs_render` |
| **P6.4 Investigate canvas** | M6 | S2–S5 | Cytoscape with compound nodes, styles per §10.6, expand by edge type, method/confidence filters, time slider, layouts, path finder, inspector, pin to case, PNG/GraphML export, Sigma overview over 2k nodes with ForceAtlas2 in a worker | 60 fps at 2k elements on the reference laptop |
| **P6.5 Dossiers and object pages** | M5 | S5 | Actor (six tabs), entity, address, tx, IP (enrichment with source and date), session | Every object reachable from ⌘K |
| **P6.6 Geo and Sankey** | M6 | S6–S7 | deck.gl arcs and origins with Natural Earth; ECharts Sankey from any root | Offline render verified (no tile requests) |
| **P6.7 Cases, exports, verify, audit UI** | M5 | S5–S6 | Case workspace, notes, export panel with approvals, **Verify** page with seal, audit table plus **Verify chain** | `e2e_analyst_journey` passes end to end |
| **P6.8 Govern** | M5 | S6–S7 | Models (registry, cards, promote/rollback, shadow comparison), drift heat map, users, settings (defaults and diffs), refdata, system (offline status) | Admin can promote a model and roll back |
| **P6.9 i18n, accessibility, states** | M5 | S7 | Hindi catalogue for chrome (reviewed by a native speaker), keyboard focus order, colour-independent encodings, empty/loading/error/**snapshot**/drift/demo states | `e2e_hindi_locale_smoke`, `e2e_snapshot_fallback`; an axe-core check with no critical issues |

**P6 exit:** two people outside the team complete "find the ransomware operator and export a case" unaided in under 10 minutes. We watch, take notes and fix what confused them.

---

## P7 — The signature features · S5–S8 (2 – 29 Nov) · mixed

> **Goal.** The things no other team will have. Each must be demoable in under 60 seconds and must survive an expert asking "is that real?"

### P7.1 — Wire ⇄ Ledger Replay · 5 d · M6 + M4
- **API:** `GET …/tx/{txid}/propagation` (§9.3.5):
  - node positions from a server-side layout of the observed sub-network (sensors plus candidates);
  - events from `obs`, skew-corrected;
  - **posterior checkpoints computed by re-running `origin_ranker` on the observations available up to each t** (10–20 checkpoints).
- **UI:** the layout in §10.4, canvas or deck.gl animation with scrubber and speed, captions, the ledger strip, keyboard control.
- **Tests:** `e2e_replay_plays`, `test_propagation_posterior_monotone_information` (the final checkpoint equals E10's output).

### P7.2 — Adversary mode and the red-team report · 4 d · M2 + M4
- **Build:** knob wiring (§5.7), `evals/redteam.py` sweeps, curves and break points, the site page, a Lab UI list of reports.
- **Done when:** the red-team page is published, with an honest summary paragraph.

### P7.3 — Feedback loop: retrain, shadow, promote · 4 d · M4 + M1 + M5
- **Build:**
  - `retrain` job (§7.7): label mapping, weighting, candidate artefact;
  - shadow scoring on the latest run;
  - comparison on held-out analyst labels and `test-rand`;
  - Govern UI with a before/after precision@20;
  - promotion through the gate.
- **Tests:** `test_retrain_uses_feedback_labels`, `test_promotion_blocked_below_threshold`.
- **Demo:** dismiss 3 false positives → retrain → precision@20 moves.

### P7.4 — Model registry UI, cards, drift view · 3 d · M4 + M5
- **Build:** card rendering (§7.5), metrics with CIs and baselines, calibration plots, per-pack tables; the drift heat map; "scored under drift" banners.

### P7.5 — Scenario Studio · 3 d · M2 + M5
- **Build:** preset picker, parameter form with ranges, knob sliders, seed; generate job → dataset; realism report view. In demo mode, presets only.

### P7.6 — Academy · 4 d · M2 + M5
- **Build:**
  - challenge definitions from the `academy-*` worlds (3–6 questions each);
  - server-side scoring (truth never reaches the client);
  - timer and leaderboard;
  - "watch the engine solve it";
  - the **judge challenge** preset (§17.10).
- **Tests:** `test_academy_answers_never_sent_to_client`.

### P7.7 — Interoperability exports · 2 d · M3
- **Build:** MISP event (`btc`, `btc-wallet`, `btc-transaction`, `coin-address`, `ip-src`; tags for grade and families), STIX 2.1 via `misp-stix`, GraphML/GEXF (NetworkX), i2-importable `entities.csv`/`links.csv`, PDF report template.
- **Tests:** `test_misp_export_valid` (schema), `test_graphml_roundtrip`, `test_csv_injection_neutralised`.

### P7.8 — Sensor-coverage planner `[STRETCH]` · 4 d · M2 + M6
- **Build:** §11.6 on `arrivals.npz`: strategies, greedy marginal gain, the curve and map. Lab UI.

### P7.9 — Elliptic++ external validity `[STRETCH]` · 2 d · M4
- **Build:** §7.8. A one-off notebook turned into a script, results in the write-up.

### P7.10 — GraphSAGE comparison `[STRETCH]` · 2 d · M4
- **Build:** a PyTorch Geometric experiment in `experiments/` (**not** in the runtime image). Results table in the write-up: "trees vs GNN on our worlds".

**P7 exit:** Replay, red-team, feedback loop, cards and drift, Studio, Academy and interop are each demoable in under 60 s. The `[STRETCH]` items ship only if P8 is not at risk.

---

## P8 — Hardening, packaging & documentation · S7–S9 (16 Nov – 6 Dec) · M1 lead

> **Goal.** Make it boring to install, hard to break and easy to verify. Write down what we built, honestly.

### P8.1 — Security pass · 3 d · M1 (+ everyone reviews their module)
- **Checklist:** walk §13 line by line. Run the full security test set (XXE, bombs, injection, RBAC matrix, refresh reuse, lockout, export approvals, object-level authorisation). Check headers and CSP on both targets. Run dependency and licence scans clean. Review secrets handling.
- **Done when:** every §13 test is green and the threat-model table is updated with anything found.

### P8.2 — Performance and load · 3 d · M1 + M3
- **Build:** `scripts/bench.py` (ingest, stage timings, memory), a k6/Locust script (20 users), profiling of the top 3 hot spots (py-spy), fixes.
- **Done when:** §14.3 targets are met, or the real numbers are published with the gap explained.

### P8.3 — Air-gap bundle and installer · 3 d · M1
- **Build:** `make-bundle.sh` (§12.5.3), `install.sh`, `selfcheck.sh`, `upgrade.sh`, `uninstall.sh`, `README-AIRGAP.txt`; splitting over 2 GiB; optional cosign signature.
- **Done when:** a teammate who has never installed it goes from a USB stick to the hero demo on a clean laptop with **Wi-Fi off** in **≤ 15 minutes**, on camera.

### P8.4 — The offline verification suite, complete · 2 d · M1
- **Build:** everything in §12.9 wired into `ci.yml` and `release.yml`, plus the release-time bundle scan.
- **Tests:** `release_bundle_smoke`.

### P8.5 — Demo hardening · 2 d · M1 + M5
- **Build:** everything in §12.7: snapshot fallback bundle, caps, TTL purge, nightly reset with banner, rate limits, uptime monitor, status badge, watermarking.
- **Tests:** `e2e_snapshot_fallback`, `test_demo_upload_ttl_purge`.

### P8.6 — Documentation and the technical write-up · 4 d · M6 + M4 (+ everyone)
- **Write-up `docs/technical-writeup.md`**, rendered to PDF and the docs site (R-PS-19). Target ~8–12 pages:
  1. problem and approach;
  2. data contract and synthetic world;
  3. the engine;
  4. **model choice with the baseline comparisons**;
  5. **explainability method** (TreeSHAP, counterfactuals, evidence envelopes, calibration);
  6. evaluation and red-team results;
  7. limitations;
  8. security and lawful use.
- **Also:** one model card per model, the user guide (task-based, with screenshots), runbooks (install, upgrade, backup/restore, refdata update), and the docs site navigation.

### P8.7 — Backup/restore drill · 1 d · M1
- **Build:** a timed `sutradhar backup` → wipe → `restore` → `audit verify` → `selfcheck`. The time goes in the runbook.

### P8.8 — Release v1.0.0 · 1 d · M1
- **Build:** tag, release notes, bundle, SBOMs, docs PDF. The repository and images go public per D21. The showroom is pinned to the release image.

**P8 exit:** every `R-PS-*` test green on the release commit · bundle published · write-up published · showroom on the release · the metrics page shows the release's numbers.

---

## P9 — Finale readiness · S9–F (30 Nov → finale) · everyone

> **Goal.** Nothing new. Everything rehearsed.

| Sub-phase | Detail |
|---|---|
| **P9.1 Freeze and bug bash** | Freeze on Sunday 6 Dec `[DEFAULT]`. Only fixes after that, each with a test. Two-hour team bug bash on the showroom and the bundle. |
| **P9.2 Surprise-dataset drills** | M2 prepares **three unseen layouts** (new column names, XML nesting, mixed units, missing fees). Each teammate must take one from upload to published leads in **< 15 minutes** using only the UI. This is the rehearsal for NTRO handing us their file. |
| **P9.3 Pitch assets** | The deck (SIH format: problem → approach → architecture → live demo → numbers from the metrics page → security and lawful use → impact); a **3-minute video** (offline run, hero story); the **5-minute live script** (§17.10); **Q&A drills** (§17.11), each teammate owning the questions about their module. |
| **P9.4 Judge challenge** | The Academy preset loaded, with a timer. The script for inviting judges to try it. |
| **P9.5 Contingency kit** | **Two laptops** with the bundle installed and tested offline · the bundle on **two USB sticks** · the showroom plus **snapshot mode** as a fallback · the video stored locally · a printed one-page architecture and a printed metrics summary · a charger plan. We do not depend on venue Wi-Fi at any point. |

**P9 exit:** three full dry runs within time · every member can run the demo alone · the contingency kit has been physically checked.

---

## 15.12 Standing rules across every phase

1. **Always deployable.** `main` deploys to the showroom automatically. A broken `main` stops the line: whoever broke it fixes it before anything else.
2. **Sunday demo.** Every sprint ends with a two-minute recording of what changed, posted to the team channel.
3. **No requirement without an ID. No "done" without a passing test** recorded in `docs/requirements.csv`.
4. **`docs/INVARIANTS.md` and §17.15 are pasted into every AI coding session.**
5. **An ADR for every decision a teammate might otherwise reverse** (§16.3).
6. **Thresholds are settings, not constants.** A code review rejects magic numbers in the engine.
7. **The metrics page is the truth.** No number goes in the deck or the pitch that is not on the metrics page for the commit being demoed.
8. **Never tune on `hero` or `test-rand`.** Hero is a story. `test-rand` is an exam.

## 15.13 If we fall behind — the scope-cut order

Cut from the top. **Never cut the bottom block.**

1. P7.8 sensor planner `[STRETCH]`
2. P7.10 GraphSAGE comparison `[STRETCH]`
3. P7.9 Elliptic++ check `[STRETCH]`
4. P7.6 Academy (keep one challenge as a static script)
5. P7.5 Scenario Studio UI (keep the CLI)
6. Hindi UI (keep i18n scaffolding)
7. P6.6 Sankey (keep geo)
8. Interop: keep MISP and GraphML, drop STIX and i2
9. P7.3 retrain UI (keep the CLI retrain, show the before/after numbers in the deck)

**Never cut:** any `R-PS-*` item · offline guarantees (I1, I11) · evidence envelopes · the evidence pack and verify · calibration · the metrics page · **Replay** · the air-gap bundle.

---


# PART 16 — WHAT WE NEED FROM YOU, RISKS, AND THE DECISION LOG

## 16.1 What we need from you

Every item has a **running default**, so nothing below blocks writing code today. The ones marked ⚠️ block something real if they arrive late.

> **How to hand over secrets.** Never paste tokens, passwords or keys into chat or commit them to git. Enter them directly into the GitHub / Render / Vercel dashboards, or into a local `.env` that is git-ignored. Where I need to run something with a credential, I will give you a command to run yourself.

### Needed in Sprint 0 (by Sunday 4 Oct)

| # | What | Why / what it unblocks | Running default |
|---|---|---|---|
| ⚠️ **OPEN-01** | **Product name.** Keep *Sutradhar*, or pick another | Package names, repo name, domain, UI. Renaming later touches everything. | *Sutradhar* |
| ⚠️ **OPEN-02** | **Team roster:** six names, GitHub usernames, who takes M1–M6 (§15.1), team lead, SIH team name/ID | Ownership, branch protection, CODEOWNERS, the deck | Roles unassigned; the team lead assigns them on day 1 |
| ⚠️ **OPEN-03** | **SIH status:** was the idea submitted and accepted for SIH26146 before the portal closed (it showed 500/500 on 30 Sep)? Any portal/SPOC messages since? | Priorities and the story in the deck | Assume in; build regardless |
| ⚠️ **OPEN-05** | **GitHub home.** The repo owner's account (with the Student Developer Pack for Pro limits) or an organisation, plus the repo name. Actions enabled. | Everything in CI/CD. GHCR images. | Private repo under the team lead's account |
| **OPEN-06** | **GitHub Student Developer Pack** activated for the repo owner (ideally everyone) | Higher Actions minutes and Packages storage on private repos (§12.8) | Heavy caching, public at freeze |
| ⚠️ **OPEN-07** | **Vercel account** (Hobby) connected to the GitHub repo. Two projects: `sutradhar-web`, `sutradhar-site`. | Frontend links (P0.7) | – |
| ⚠️ **OPEN-08** | **Render account plus a payment method** for the **Standard** instance (~$25/month), *or* tell me to use **Railway** (Hobby $5/month plus usage), which you have used before | The demo API link (P0.7) | Render Standard, Singapore |
| ⚠️ **OPEN-08a** | A **GitHub personal access token (classic) with `read:packages`**, entered as a **Registry Credential in Render** (name it `ghcr`) | Render pulling our private GHCR image | – |
| **OPEN-10** | **UptimeRobot** (or BetterStack) free account | The status badge on the landing page | Add in P8.5 |
| ⚠️ **OPEN-11** | **Laptop specs** for every teammate (CPU cores, RAM, disk, OS), and which machine is the **finale reference machine** (need ≥ 8 cores / 16 GB) | Performance targets, the bundle smoke test, the finale plan | Targets assume 8 vCPU / 16 GB |
| **OPEN-12** | **Docker Engine + Compose v2** installed on every dev machine (Arch: `docker`, `docker-compose`; Windows: WSL2 + Docker Desktop; macOS: Docker Desktop) | `make dev`, the offline stack | – |
| **OPEN-14** | **Budget approval** (~₹6,500–7,500 through December, almost all Render) and who pays | Render Standard | – |

### Needed later (date shown)

| # | What | Needed by | Running default |
|---|---|---|---|
| ⚠️ **OPEN-04** | **Finale date and nodal centre**, as soon as announced | S5 | Feature freeze 6 Dec |
| **OPEN-09** | **Domain name** (optional, e.g. `sutradhar.<tld>`), registrar access for DNS | S7 | `*.vercel.app` + `*.onrender.com` |
| **OPEN-13** | **Kaggle account + API token** (only for the original Elliptic experiments) | S8 (stretch) | Elliptic++ from its Google Drive link instead |
| **OPEN-15** | A teammate who reads **Hindi** fluently to review UI strings | S7 | English only if nobody can review (no machine-translated UI) |
| **OPEN-16** | Brand preferences (logo, colours) | S2 | Tokens in §10.5 (saffron accent on dark) |
| **OPEN-17** | Repo and image **visibility timing** | S9 | Private → **public at feature freeze** (D21) |
| **OPEN-18** | Anything from SIH/NTRO: mentor notes, **any sample dataset**, the evaluation rubric, finale format | Whenever it arrives | Our own worlds and schema-zoo |
| **OPEN-19** | The **image and 35-line paste** from your first message. Neither reached me. | Now, if it contained team notes or constraints | – |
| **OPEN-20** | Where the demo video lives (unlisted YouTube or Drive) | S9 | Unlisted YouTube |
| **OPEN-21** | Institute name, SPOC, team name exactly as on the portal (title slide, docs) | S9 | – |

### What we do **not** need (say no if anyone suggests it)

- ✗ No paid APIs of any kind. ✗ No LLM / OpenAI / Anthropic keys. The product has no LLM.
- ✗ No blockchain node, RPC endpoint or explorer API. ✗ **No Solana** (§16.3 D18).
- ✗ No MaxMind account (DB-IP Lite needs no signup). ✗ No GPU or cloud ML platform.
- ✗ No real traffic data, ever, in the repo or the showroom.

## 16.2 The risk register

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| **R1** | ⚠️ **Our synthetic world is unrealistic, so the models do not transfer to NTRO's data** | Strong numbers on our worlds, weak on theirs | Domain randomisation (§5.11), realism report (§5.12), heuristic and unsupervised components that do not depend on training, **drift detection** (§7.6), feedback recalibration (§7.7), the Elliptic++ external check (§7.8), capability-driven degradation (chain-only mode). **Say it openly in the pitch.** |
| **R2** | Origin attribution is weak for some observation models (sparse sensors, single observation per tx, heavy Tor) | The NET story looks thin on some data | The explicit `p_unobservable`, per-model reporting, the `single` model labelled "as reported", the sensor planner showing what more coverage would buy |
| **R3** | ⚠️ **NTRO's finale file has an unexpected schema** | A demo stall in front of the people who matter most | Auto-mapper, mapping wizard, **schema-zoo**, **surprise drills** (P9.2), capability detection, V-rules that explain rather than crash |
| **R4** | Scope overload: six students, seven modules | Everything at 60% | Tiers, the scope-cut order (§15.13), walking skeleton first, weekly demos, "never cut" list |
| **R5** | Performance on a finale laptop | Slow demo | Benchmarks from S4, streaming and bounded-memory ingest, `ENGINE_THREADS`, **pre-analysed demo datasets in the bundle** |
| **R6** | Showroom outage or cold start during judging | Broken link | Paid instance (no sleep), **snapshot fallback**, uptime monitor, local video |
| **R7** | An offline violation slips in (Google Fonts, CDN, Swagger assets, telemetry) | Contradicts R-PS-01 in front of NTRO | I1/I11 tests on every PR, the bundle scan, the offline e2e |
| **R8** | CoinJoins or mega-clusters corrupt clustering | Wrong actors, wrong leads | E04 before E05, the mega-cluster split, per-wallet metrics, *heuristic* labelling |
| **R9** | Determinism breaks (thread counts, unordered writes) | The reproducibility claim fails live | `test_run_is_deterministic` nightly on hero, explicit `ORDER BY`, fixed threads, seeded RNG |
| **R10** | GitHub Actions minutes or GHCR storage limits on a private repo | CI stalls, image pushes fail | Caching, path filters, retention of 3 versions, Student Pack Pro, public at freeze |
| **R11** | Key-person dependency | One sick day stalls the critical path | The pairing rule (§15.1), ADRs, `docs/`, the Sunday demos |
| **R12** | Judges read "deanonymisation" as an ethics problem | Credibility loss with NTRO | §13.7: leads not verdicts, the Auditor role, hedged language, no geographic profiling, synthetic-only |
| **R13** | Integration hell in a six-person monorepo | Late-breaking conflicts | Contract-first schemas (P0.2), module ownership, trunk-based, generated TS client, CI on every PR |
| **R14** | Accidental tuning on hero or the test set | Inflated numbers that collapse in Q&A | Rule 8 (§15.12), frozen seeds, targets frozen at review #2 |
| **R15** | Data and font licence or attribution slips | Embarrassing in a government evaluation | Attribution in the UI and About, the licence check in CI (§13.5) |
| **R16** | A finale laptop lacks Docker or RAM | Can't run the product | OPEN-11 now, test the bundle on the weakest machine in P8.3, two prepared laptops (P9.5) |
| **R17** | Idea submission or acceptance status unknown (the PS was full) | – | OPEN-03. Build regardless: the work stands on its own as a product and a portfolio piece. |

## 16.3 The decision log

Recorded so decisions are not silently reopened. Each becomes an ADR in `docs/adr/`.

| # | Decision | Because |
|---|---|---|
| **D1** | **Offline-first. One codebase, two targets:** air-gapped product plus cloud showroom | The PS demands offline. Judges need links. The same images satisfy both, and that is a strength to say out loud. |
| **D2** | **Modular monolith** (FastAPI) **plus one worker process.** No microservices, no serverless backend | Team size, offline install simplicity, a stateful graph engine (§3.2) |
| **D3** | Python for engine, API and generator; TypeScript for the UI | The ML, graph and data ecosystem is Python. A typed OpenAPI contract bridges the two. |
| **D4** | FastAPI over Django | A thin API over a heavy engine, typed models → OpenAPI → generated TS client, async SSE. Django's strengths (admin, ORM for 100 tables) are not our problem. |
| **D5** | **Two stores:** app DB (Postgres/SQLite) for workflow; an **immutable DuckDB file per run** for analytics and evidence | Workflow is mutable and relational. Evidence must be immutable and hashable. One file per run *is* the evidence artefact. |
| **D6** | A hand-rolled job table (`SKIP LOCKED`; embedded in SQLite demo) instead of Celery/Redis | One fewer service in the air-gapped bundle. It works identically on both databases. The queue is simple. |
| **D7** | **LightGBM as the model family**, with exact TreeSHAP via `pred_contrib` | Trees beat GNNs on this class of data (Weber et al. 2019; Elliptic++). CPU-only, deterministic, and exact explanations without the `shap`/numba stack in the image. |
| **D8** | Randomized-SVD embeddings, not node2vec/torch | Deterministic, light, fast. torch stays out of the runtime image. node2vec is a stretch comparison. |
| **D9** | **Build our own synthetic world** (UTXO economy plus P2P propagation plus sensors), adapting AMLSim/AMLworld typologies | Existing generators model bank accounts, not UTXOs, and none has a network layer. The PS asks for synthetic data "modelled on real Bitcoin P2P/transaction fields". |
| **D10** | Rebuild UTXO links by **(address, amount) matching** when prevouts are absent | The PS minimum fields give aligned `input_amounts[]`. Exact-amount matching recovers the graph almost perfectly, where address-only matching would not. |
| **D11** | **Origin attribution is a learned ranker with an explicit "not observable" probability.** First-spy is the baseline to beat, not the method. | Theory (Fanti & Viswanath 2017) and practice (Biryukov 2014; Koshy 2014) say the richer, structure-aware estimators dominate. Honest abstention beats confident wrong IPs. |
| **D12** | **CIOH is a lead generator, not truth.** CoinJoin-gated, mega-cluster-split, labelled *heuristic*. Merges below 0.9 need a human. | Müller et al. 2026 (per-wallet precision 0.36 / recall 0.44 on real EU ground truth); Iknaio's "address clustering is not evidence" |
| **D13** | **Leads, not verdicts.** Calibrated p, grades from independent evidence families, hedged language, counterfactuals | This is what an intelligence evaluator needs to act responsibly, and what separates us from "99% accuracy" entries. |
| **D14** | **DB-IP Lite** (CC BY 4.0) as the GeoIP/ASN source; IPinfo Lite optional; no GeoLite2 | No signup, direct download, offline-friendly licence. GeoLite2's account and 30-day-deletion EULA fit air-gapped use badly. |
| **D15** | Bearer tokens (JWT access plus rotating refresh), no cookies | Works across the cross-site demo domains without CSRF machinery. Strict CSP limits token-theft risk. |
| **D16** | **Vercel for static frontends only. Render Standard (image-backed from GHCR) for the demo API.** Railway as the documented alternative. | Verified limits: Vercel Hobby functions (2 GB / 300 s / 4 active CPU-h per month) and Render Free (sleeps, 30-day DB) are the wrong shape (§12.6.2). |
| **D17** | Demo mode = SQLite, a baked pre-analysed hero world, nightly reset, **snapshot fallback** | Nothing expires. The first request is instant. The link cannot show a broken page. |
| **D18** | **No Solana, no blockchain anchoring.** Local hash-chained audit plus SHA-256 hash reports. | Offline requirement; OPSEC (a public chain leaks the existence and timing of investigations); no trust benefit from a one-party chain. The hash report already matches BSA s.63's certificate. |
| **D19** | **No LLM in the core.** Deterministic templates for narratives. | Offline; no hallucination liability in forensic output; templates are auditable and testable (language guard). |
| **D20** | Evidence packs aligned to **BSA 2023 s.63** hash-report expectations; the platform never signs for a human | Useful to Indian law enforcement as-is, without pretending to be a legal instrument |
| **D21** | Repo and images **private until feature freeze, then public** `[DEFAULT]` | Protects the work from 499 competing teams during the build. Public at the finale for judges and for CI limits. |
| **D22** | **No country or ASN identity features** in `lead_ranker`, only infrastructure type and diversity | Prevents geographic profiling. Tested by country ablation (§13.7). |
| **D23** | **Services are never ACTOR leads. Victims are separated.** CASHOUT is its own lead type. | Exchanges are where cases end (lawful notice), not suspects. Victims must not become suspects. |
| **D24** | Runs are **full recomputations over a window**, not incremental updates | Keeps reproducibility (I4) simple and true. Fast enough at our scale. |

---


# PART 17 — APPENDICES

## 17.1 Accounts and credentials to set up

| Owner | Item | Where it is configured | When |
|---|---|---|---|
| Team lead | GitHub repository (private), Actions enabled, branch protection on `main`, CODEOWNERS from the roster | GitHub | S0 |
| Team lead | GitHub Student Developer Pack (Pro limits) | education.github.com | S0 |
| Team lead | Vercel (Hobby) → import repo → projects `sutradhar-web` (`apps/web`) and `sutradhar-site` (`apps/site`) | Vercel dashboard | S1 |
| Team lead | Render account + payment method → Registry Credential `ghcr` (GitHub username + classic PAT with `read:packages`) → Blueprint from `deploy/render/render.yaml` | Render dashboard | S1 |
| Team lead | GitHub Actions secret `RENDER_DEPLOY_HOOK` (from the Render service's Settings) | GitHub → Settings → Secrets | S1 |
| M1 | UptimeRobot monitor on `https://<api>/api/health` + public status page | UptimeRobot | S8 |
| Optional | Domain + DNS (`app.` → Vercel, `api.` → Render) | Registrar | S7 |
| Optional | `COSIGN_PRIVATE_KEY` / `COSIGN_PASSWORD` for bundle signing (key kept offline) | GitHub secrets | S9 |
| Optional | Kaggle API token (original Elliptic dataset) | local `~/.kaggle/kaggle.json`, never committed | S8 |

**Never needed:** LLM keys, blockchain RPC keys, MaxMind keys, cloud GPU accounts.

## 17.2 Environment variables

| Variable | Used by | Modes | Default / example | Secret |
|---|---|---|---|:-:|
| `APP_MODE` | api, worker, cli | all | `dev` · `demo` · `airgap` | |
| `DATABASE_URL` | api, worker | all | `postgresql+psycopg://sutradhar_app:…@db:5432/sutradhar` · `sqlite:////data/app.sqlite` | ✓ |
| `MIGRATION_DATABASE_URL` | `sutradhar migrate` | airgap | owner-role URL | ✓ |
| `DATA_DIR` · `MODELS_DIR` · `REFDATA_DIR` · `REFDATA_OVERRIDE_DIR` | api, worker | all | `/data` · `/models` · `/refdata` · `/refdata-override` | |
| `JWT_SECRET` | api | all | 32+ random bytes | ✓ |
| `JWT_ACCESS_TTL_MIN` · `JWT_REFRESH_TTL_H` | api | all | `20` · `12` | |
| `OFFLINE_GUARD` | api, worker | all | `on` (demo, airgap, ci) · `warn` (dev) | |
| `ENGINE_THREADS` | worker | all | `8` | |
| `WORKER_CONCURRENCY` | worker | airgap, dev | `2` | |
| `EMBEDDED_WORKER` | api | demo | `true` | |
| `CORS_ORIGINS` · `CORS_ORIGIN_REGEX` | api | demo | `https://sutradhar-web.vercel.app` · `^https://sutradhar-web-[a-z0-9-]+-<team>\.vercel\.app$` | |
| `DEMO_ADMIN_PASSWORD` | api | demo | set in Render dashboard | ✓ |
| `DEMO_UPLOAD_MAX_MB` · `DEMO_UPLOAD_MAX_ROWS` · `DEMO_UPLOAD_TTL_MIN` | api | demo | `25` · `200000` · `60` | |
| `DEMO_RESET_CRON_UTC` | api | demo | `30 21 * * *` (= 03:00 IST) | |
| `LOG_LEVEL` · `LOG_FORMAT` | all | all | `info` · `json` | |
| `BIND` · `VERSION` | compose | airgap | `127.0.0.1` · `1.0.0` | |
| `OWNER_DB_PASSWORD` · `APP_DB_PASSWORD` | compose / db-init | airgap | generated by `install.sh` | ✓ |
| `ADMIN_BOOTSTRAP_EMAIL` | `install.sh` | airgap | `admin@local` (password printed once) | |
| `VITE_API_BASE_URL` | web build | demo, dev | `https://<api>.onrender.com` · `/` (airgap: same origin) | |
| `VITE_APP_MODE` | web build | all | `demo` · `airgap` · `dev` | |
| `VITE_SNAPSHOT_URL` | web build | demo | `/snapshot/hero.json.gz` | |
| `RENDER_DEPLOY_HOOK` | GitHub Actions | ci | from Render | ✓ |

## 17.3 The settings that carry every `[DEFAULT]`

Every placeholder in this document is one of these rows. Changing a value changes a row (audited), never code. A value that needs a code change to alter is a design failure, and goes in the decision log.

```
engine.seed                         2026
engine.threads                      8
ingest.amount_unit                  auto        btc | sat | auto
ingest.naive_timestamp_tz           UTC
ingest.reject_rate_hold             0.20
ingest.decompression_ratio_max      200
ingest.max_record_bytes             1048576
coinjoin.tau                        0.50
cluster.mega_min_size               5000
cluster.mega_p99_multiple           50
cluster.borderline_coinjoin_low     0.30
change.max_outputs                  4
change.decide_min_p                 0.50
change.merge_min_p                  0.95
peel.min_ratio                      3
peel.max_hops                       200
peel.chain_lead_min_p               0.60
peel.chain_lead_min_hops            3
motifs.windows_h                    [24, 72]
motifs.fan_k                        5
timing.session_gap_min              30
origin.max_candidates               20
origin.edge_min_p                   0.20
origin.edges_top_k                  3
control.co_origin_min_strength      0.50
control.crowd_threshold_p           0.50
er.auto_merge_min_p                 0.90
er.suggest_min_p                    0.60
er.max_pairs                        200000
er.knn_k                            10
er.knn_min_cos                      0.80
risk.hop_decay                      0.90
risk.max_hops                       40
risk.min_taint_frac                 0.0001
risk.stop_at_services               true
risk.ppr_damping                    0.85
risk.paths_top_actors               500
risk.paths_k                        3
cashout.min_taint_btc               0.05
cashout.min_taint_frac              0.20
anomaly.n_estimators                300
lead.actor_min_p                    0.40
lead.grade_a_min_p                  0.80
lead.grade_a_min_families           3
lead.grade_b_min_p                  0.60
lead.grade_b_min_families           2
lead.grade_c_min_p                  0.40
lead.family_support_min_logodds     0.05
lead.tx_taint_min_frac              0.20
lead.tx_anomaly_min_pct             0.995
lead.ip_min_control_p               0.60
priority.value_scale                10
priority.recency_half_life_days     14
priority.actionable_bonus           0.25
priority.actionable_min_origin_p    0.60
explain.top_supporting              6
explain.top_opposing                2
explain.cf_max_steps                5
explain.subgraph_max_nodes          150
tz.min_txs                          20
drift.psi_moderate                  0.10
drift.psi_major                     0.25
retrain.min_new_labels              50
retrain.analyst_label_weight        5
retrain.recalibrate_min_labels      200
runs.keep_last_per_dataset          5
retention.access_log_days           90
auth.lockout_failures               5
auth.lockout_minutes                15
ui.timezone                         Asia/Kolkata
ui.default_locale                   en
```

## 17.4 The requirement traceability matrix

`docs/requirements.csv` is the live artefact. CI renders it into the docs site with status colours.

```csv
id,source,statement,module,screen,endpoint,db_objects,test_id,phase,status
R-PS-01,PS objective,"Complete system (offline)",PLT,System,GET /system/info,,test_offline_pipeline_no_network;test_web_makes_no_external_requests,P0|P8,
R-PS-02,PS objective,"Ingest bulk metadata in CSV/JSON/XML",M1,Ingest,POST /datasets,obs;tx;txin;txout,test_three_formats_same_digest,P2,
R-PS-03,PS objective,"Correlate network-layer with blockchain-layer data",M2,Lead→Network;Replay,GET /runs/{id}/tx/{txid}/propagation,origin;control;co_origin,test_origin_beats_first_spy,P4,
R-PS-06,PS challenge,"Entity/transaction graph linking IPs, wallets, transactions",M2/M4,Investigate,GET /runs/{id}/graph/neighbors,flow;entity_member;origin;control,test_every_edge_has_evidence_envelope,P3,
R-PS-08,PS challenge,"Ranked explainable alert list with confidence",M3,Triage;Lead→Why,GET /runs/{id}/leads,lead;lead_contrib,test_every_lead_has_reason_grade_calibrated_p,P5,
R-PS-13,PS focus,"Propagate risk from seed illicit wallets",M2,Lead→Path to seed,GET /leads/{id}/explanation,risk;risk_path,test_taint_stops_at_services,P5,
R-ENG-031,D12,"CoinJoin txs never contribute CIOH merges",M2,,,entity_member;cj,test_cioh_excludes_coinjoin,P3,
R-CAS-009,§8.7,"Evidence pack verifies independently",M5,Verify,POST /verify,exports;verifications,test_evidence_pack_verifies,P6,
R-SEC-011,§13.4,"CSV formula injection neutralised",SEC,,,,test_csv_injection_neutralised,P2,
…
```

## 17.5 Sample records — one observation in all three formats

The examples use **documentation IP ranges** (RFC 5737) and **specification test-vector addresses** (BIP-173/350). They point at nothing real.

**CSV** (arrays as JSON-in-cell):
```csv
timestamp,src_ip,src_port,dst_ip,dst_port,txid,input_addresses,input_amounts,output_addresses,output_amounts,fee,script_type,geo_country,asn
2026-08-21T19:44:02.113204Z,198.51.100.23,51544,203.0.113.7,8333,9c1e5b7d2a4f6e8c0b1d3f5a7c9e2b4d6f8a0c2e4b6d8f0a1c3e5b7d9f2a4c6e,"[""bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4""]","[0.42]","[""bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"",""1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2""]","[0.031,0.3885]",0.0005,p2wpkh,IN,55836
```

**JSON** (one object of an array, or one NDJSON line):
```json
{"timestamp": "2026-08-21T19:44:02.113204Z",
 "src_ip": "198.51.100.23", "src_port": 51544, "dst_ip": "203.0.113.7", "dst_port": 8333,
 "txid": "9c1e5b7d2a4f6e8c0b1d3f5a7c9e2b4d6f8a0c2e4b6d8f0a1c3e5b7d9f2a4c6e",
 "input_addresses": ["bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"], "input_amounts": [0.42],
 "output_addresses": ["bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
 "output_amounts": [0.031, 0.3885], "fee": 0.0005, "script_type": "p2wpkh", "geo_country": "IN", "asn": 55836}
```

**XML** (nested style; the wrapped style is also accepted via the profile):
```xml
<capture>
  <event>
    <timestamp>2026-08-21T19:44:02.113204Z</timestamp>
    <src_ip>198.51.100.23</src_ip><src_port>51544</src_port>
    <dst_ip>203.0.113.7</dst_ip><dst_port>8333</dst_port>
    <txid>9c1e5b7d2a4f6e8c0b1d3f5a7c9e2b4d6f8a0c2e4b6d8f0a1c3e5b7d9f2a4c6e</txid>
    <inputs>
      <input><address>bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4</address><amount>0.42</amount></input>
    </inputs>
    <outputs>
      <output><address>bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0</address><amount>0.031</amount></output>
      <output><address>1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2</address><amount>0.3885</amount></output>
    </outputs>
    <fee>0.0005</fee><script_type>p2wpkh</script_type><geo_country>IN</geo_country><asn>55836</asn>
  </event>
</capture>
```

**What ingestion makes of this row:**
- Amounts become satoshis: 42,000,000 → 3,100,000 + 38,850,000, and the fee checks out at 50,000.
- The timestamp becomes `1787341442113204` µs UTC.
- The output script types are inferred as `p2tr` and `p2pkh`.
- The provided `geo_country`/`asn` are kept as `*_src`. Enrichment of a documentation IP returns nothing, so the X-ray shows a V15 note.

## 17.6 Built-in mapping profiles

| Profile | Matches |
|---|---|
| `canonical-v1` | Our canonical exporter (all formats) |
| `renamed-v1` | The generator's `renamed` variant (`tx_hash`, `source.ip`, `vin_addrs`…) |
| `indexed-arrays-v1` | `input_address_0…n` / `input_amount_0…n` columns |
| `xml-wrapped-v1` | `<input_addresses><address/>…</input_addresses>` layout |
| `single-obs-v1` | One record per transaction, no relay repetition |
| `identity` | Column names already canonical |

New profiles are created in the wizard and saved with a version. `ntro-*` profiles get added the moment we see NTRO's layout.

## 17.7 The evidence-pack README (template)

```
SUTRADHAR EVIDENCE PACK
Case:        {case_id} — {case_title}
Exported:    {ts_ist} IST ({ts_utc} UTC) by {user} ({role}); approved by {approver}
Run:         {run_id}   result_digest {result_digest}
Software:    Sutradhar {version} ({git_sha}), image {image_digest}

HOW TO VERIFY (no special software needed):
  1. sha256sum -c SHA256SUMS          → every line must read OK
  2. Compare hash_report.txt with SHA256SUMS (identical values, SHA-256)
  3. With Sutradhar: `sutradhar verify <this.zip>` (offline) for reference and audit-chain checks,
     and `--reproduce <dataset>` to re-run the analysis and compare the result digest.

WHAT THIS IS: investigative leads with calibrated confidence and their supporting evidence.
WHAT THIS IS NOT: a determination of identity or guilt. Clustering heuristics are labelled as such.
Electronic-record certification (e.g. BSA 2023 s.63) is made by the responsible officer; the
hash values required for it are in hash_report.txt.
```

## 17.8 CI workflow outline (`ci.yml`)

```yaml
name: ci
on: [pull_request, push]
concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }
permissions: { contents: read, packages: read }
jobs:
  py:
    runs-on: ubuntu-24.04
    services:
      postgres: { image: "postgres:17-alpine", env: { POSTGRES_PASSWORD: ci }, ports: ["5432:5432"] }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6            # pin to a released tag
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run pyright
      - run: uv run lint-imports                 # import-linter contract (I18)
      - run: uv run pytest -m "not slow" --maxfail=1
  js:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm }
      - run: pnpm install --frozen-lockfile
      - run: pnpm -r lint && pnpm -r typecheck && pnpm -r test
      - run: ./scripts/gen-client.sh && git diff --exit-code packages/ts-client
      - run: pnpm --filter @sutradhar/web build && node scripts/check-no-external-urls.mjs apps/web/dist
  offline-engine:
    needs: [py]
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: docker buildx build -f deploy/docker/api.Dockerfile -t sutradhar-api:ci --load .
      - run: docker run --rm --network none sutradhar-api:ci selftest --scenario tiny     # I1
  e2e:
    needs: [py, js]
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f deploy/compose/compose.offline-test.yaml up --build --abort-on-container-exit --exit-code-from playwright
```
*(Action versions shown are illustrative. Pin each to a current release tag or commit SHA when creating the file.)*

---


## 17.9 Developer quick start

```bash
git clone <repo> sih26146 && cd sih26146
make setup      # uv sync · pnpm install · pre-commit install · scripts/fetch-refdata.sh (needs network once)
make dev        # compose.dev (postgres) + api --reload + worker + vite → http://localhost:5173
make world      # sutradhar gen run --scenario tiny --seed 1 --out worlds/tiny
make demo-data  # hero world → ingest → run → demo-data/ (baked into the demo image)
make test       # pytest -m "not slow" + vitest
make e2e        # compose.offline-test.yaml + Playwright (proves no egress)
make lint fmt   # ruff · pyright · import-linter · eslint · prettier
make bench      # scripts/bench.py on the hero world (§14.3)
make bundle     # air-gap bundle → dist/sutradhar-airgap-<ver>-linux-amd64/
```

On Arch, check that the engine needs no network at all:
```bash
unshare -rn uv run sutradhar selftest --scenario tiny
```


## 17.10 The five-minute live demo script

*Pre-conditions:*
- the reference laptop with the air-gapped stack running;
- **networking off** (`nmcli networking off`, shown on screen);
- the hero dataset already ingested and the run published (ingest is shown via the X-ray, not waited for);
- a second browser tab open on the metrics page (a local copy of the site in the bundle).

| Time | Beat | On screen | Line |
|---|---|---|---|
| 0:00 | Hook | Top bar: **AIR-GAPPED ✓**; terminal: no network | "NTRO sees the wire. Everyone else sees only the ledger. We fuse the two, fully offline." |
| 0:25 | Ingest | X-ray: 1.5 M rows, observation model **mixed**, 40 sensors, amount unit detected with its evidence, 0.3% rejects by rule | "Any CSV, JSON or XML. It maps unknown columns and tells you what it rejected and why." |
| 0:55 | Triage | Queue: lead #1 **ACTOR, grade A**, families NET·FLOW·TAINT·BEHAV | "Ranked by priority: confidence, value at stake and recency." |
| 1:15 | Why | Reasons: 41% of inflow traces to 3 watchlisted ransom wallets · a 23-hop regular peel chain · co-origin merge with an unlinked wallet · UTC+05:30 activity · 30% via Tor, *not observable* | "Every reason is the model's actual contribution, in hedged language. It also tells you what argues against." |
| 2:00 | **Replay** | A peel-hop tx: announcements ripple across sensors; the posterior converges to a Jio session at p = 0.8; first-spy is shown alongside | "This is the correlation the PS asks for: which IP most likely sent the money, and how sure we are, as it happens." |
| 2:45 | Follow the money | Canvas path seed → hops → **CASHOUT at EXD**; three CASHOUT leads | "This is the actionable output: a lawful notice to this exchange about this deposit address." |
| 3:20 | Evidence | Add to case → export evidence pack → **Verify** → green seal · `hash_report.txt` | "Hash report per BSA section 63. Anyone can re-verify it, and re-run it to the same digest." |
| 4:00 | Honesty | Metrics page: precision@50 on unseen worlds, origin lift vs first-spy, calibration plot, a red-team curve showing where Tor breaks attribution | "Every number here came from CI, on worlds the models never saw, including where we fail." |
| 4:40 | Close | Architecture one-pager | "Leads, not verdicts. Offline. Reproducible. Built for NTRO." Then invite the judges to the challenge. |

**Judge challenge (Academy preset `judge-01`).** *"Three minutes: which IP most likely operated wallet cluster W-17, and where did its money cash out?"* The judge uses the console. Then we click **Watch the engine solve it**: about 10 seconds, with evidence.

**Backups, in order:** second laptop (identical) → the showroom link, if a network exists → the showroom's **snapshot mode** → the local video.

## 17.11 Q&A preparation — questions we will be asked

| Question | Short answer (each teammate owns the ones about their module) |
|---|---|
| "Your data is synthetic. Why would this work on real traffic?" | Domain randomisation across 40 worlds. Realism checks. Heuristic and unsupervised components that need no training. **Drift detection that tells you when it's out of its depth.** Recalibration from analyst feedback. An external check on real labelled Elliptic++ wallets. We claim what the metrics page shows, and no more. |
| "What if the operator uses Tor or onion-only?" | Then the origin is **not observable**, and the system says so with `p_unobservable` instead of guessing. The lead then rests on the other evidence families. The red-team page shows exactly how attribution degrades with Tor share. |
| "Many users share one IP under CGNAT. Doesn't that break it?" | Attribution works at the **session** level (IP, port, time). IP-level evidence is down-weighted by crowdedness. There is a test for it (`test_session_beats_ip_under_nat`). |
| "Common-input clustering is broken by CoinJoins." | Correct. That's why CoinJoin scoring runs *before* clustering, mega-clusters are auto-split, clusters are labelled *heuristic*, uncertain merges need a human, and we report per-wallet metrics as Müller et al. (2026) recommend. |
| "Why not a GNN?" | On Elliptic, Random Forest beat GCN (F1 0.79 vs 0.63). A reproduction on Elliptic++ found XGBoost beating GraphSAGE. Trees give *exact* explanations offline. Our GNN comparison is in the write-up. |
| "Is 0.9 really 90%?" | On held-out worlds, yes: isotonic calibration, ECE on the metrics page. On new data, only after recalibration, and the drift banner warns you until then. |
| "Could this be used to surveil ordinary people?" | It is built against that: leads not verdicts, no geographic profiling features, victims excluded, human sign-off for consequential steps, an Auditor role, a hash-chained audit, access logs. Synthetic data only. |
| "How do we know results weren't tampered with?" | Immutable run files, result digests, a hash-chained audit verified with one click, and evidence packs anyone can verify offline. A re-run reproduces the same digest. |
| "Will it scale to NTRO volumes?" | Streaming, bounded-memory ingest. Columnar DuckDB. Windowed runs. Measured throughput is on the metrics page. The path to larger volumes is bigger machines and partitioned windows. No component needs the whole history in RAM. |
| "What if our file doesn't look like yours?" | "Give it to us." The mapping wizard auto-proposes a profile. We rehearsed unseen layouts to published leads in under 15 minutes. |
| "Is it real-time?" | Monitoring mode ingests batches, recomputes over a window and diffs against the last run. Latency is minutes, and watchlist hits are instant. True streaming is future work, stated as such. |
| "Why is there a cloud link if it must be offline?" | The link is a showroom on synthetic data. The product is the air-gapped bundle, built from the same images, with egress blocked two independent ways. |
| "Why should we trust origin attribution over first-spy?" | Theory: under Bitcoin's diffusion, the first-timestamp estimator degrades with node degree while structure-aware estimators stay strong (Fanti & Viswanath 2017). Practice: our lift over first-spy per observation model, on unseen worlds. |
| "Is the output admissible?" | It is built to support certification. BSA 2023 s.63 needs hash values and a hash report, which the pack provides. But the outputs are **leads**. Certification and corroboration are human and legal steps. |

## 17.12 Deck mapping

**SIH idea template (6 slides max, PDF).**

| Slide | Content |
|---|---|
| 1. Title | PS SIH26146 · NTRO · *Sutradhar: Wire + Ledger intelligence for Bitcoin traffic* · team |
| 2. Idea / solution | The fusion idea. The five lead types. Offline. "Leads, not verdicts." |
| 3. Technical approach | The one-page architecture (§3.1), the stack, a Replay screenshot |
| 4. Feasibility & viability | The generator, measured targets, risks and mitigations, the air-gap bundle |
| 5. Impact & benefits | CASHOUT leads to lawful notices, evidence packs (BSA s.63), analyst time saved, oversight features |
| 6. Research & references | Biryukov 2014 · Fanti & Viswanath 2017 · Kappos 2022 · Müller 2026 · Weber 2019 · Elliptic++ 2023 · AMLworld 2023 · plus the links |

**Finale deck (~10 slides):**
1. Problem.
2. Insight: wire + ledger.
3. Live demo (switch to the product).
4. Architecture.
5. The models vs baselines.
6. Explainability and evidence.
7. Red-team honesty.
8. Security and lawful use.
9. Deployment: air-gapped plus showroom.
10. Roadmap and ask.

## 17.13 Glossary

| Term | Meaning |
|---|---|
| **UTXO** | Unspent transaction output: a spendable "coin" created by one transaction and consumed by a later one |
| **txid** | 64-hex transaction identifier |
| **CIOH / co-spend** | Common-input-ownership heuristic: inputs spent together are assumed to be one owner's. A *heuristic*, broken by CoinJoin. |
| **Change output** | The output returning the remainder to the sender |
| **Peel chain** | A repeated pattern: a small "peel" paid out, the large change forwarded to the next hop |
| **CoinJoin** | A collaborative transaction mixing many users' coins (Whirlpool-, Wasabi- and JoinMarket-like structures) |
| **Diffusion** | Bitcoin Core's relay mechanism: announcements to each peer after independent random delays |
| **First-spy** | The baseline estimator: "the first node to tell a sensor about a transaction created it" |
| **Sensor / vantage point** | A listening node recording announcements from its peers |
| **Flow tap** | ISP-level observation of messages on links in covered networks |
| **Session** | One TCP connection's lifetime (IP, port, time window). Tighter than an IP behind NAT. |
| **NAT / CGNAT** | Many devices sharing one public IP (carrier-grade on mobile networks) |
| **ASN** | Autonomous System Number: the network operator an IP belongs to |
| **Tor exit / onion-only** | Traffic leaving the Tor network from a shared exit IP / never leaving it (unobservable as an IP) |
| **Haircut taint** | Taint split proportionally to value at each transaction |
| **PPR** | Personalized PageRank: random-walk relevance to the seed nodes |
| **Entity / Actor** | A CIOH cluster / one or more entities judged to be one operator |
| **CASHOUT** | A tainted deposit at a service: the lead that ends in a lawful notice |
| **Evidence envelope** | method + confidence + evidence refs + model version + run id, carried by every inferred edge |
| **Evidence family** | NET · FLOW · TAINT · ANOM · BEHAV. Grades count independent families. |
| **Calibration / ECE** | Making p mean what it says / how far it is from that |
| **TreeSHAP** | Exact per-feature contributions for tree models (`pred_contrib`) |
| **Counterfactual** | The smallest set of changes that would drop a lead below its grade |
| **PSI / drift** | Population Stability Index: how far current data is from the training data |
| **Domain randomisation** | Training on many worlds with randomised parameters so models learn invariances |
| **Run manifest / result digest** | The record that makes a run reproducible / the hash that proves it was |
| **Air-gapped / showroom / snapshot mode** | The offline product / the public demo / the demo's read-only fallback |
| **BSA 2023 s.63** | Bharatiya Sakshya Adhiniyam, Section 63: admissibility of electronic records (certificate with hash values) |

## 17.14 References and links

### SIH and the problem statement
- SIH portal: https://www.sih.gov.in/
- PS SIH26146 (unofficial mirror of the official listing): https://sih2026.vuce.in/ps/SIH26146
- SIH 2026 timeline (launch coverage): https://www.timesnownews.com/education/smart-india-hackathon-2026-over-220-problem-statements-released-article-155949432
- Local PS PDF: `~/Downloads/SIH26146.pdf`

### Network-layer deanonymisation (the correlation engine)
- Biryukov, Khovratovich, Pustogarov: *Deanonymisation of clients in Bitcoin P2P network* (CCS 2014): https://arxiv.org/abs/1405.7418
- Koshy: *An analysis of anonymity in Bitcoin using P2P network traffic* (PSU thesis 2014): https://etda.libraries.psu.edu/files/final_submissions/7343
- Fanti & Viswanath: *Deanonymization in the Bitcoin P2P Network* (NeurIPS 2017): https://proceedings.neurips.cc/paper/2017/hash/6c3cf77d52820cd0fe646d38bc2145ca-Abstract.html
- Fanti & Viswanath: *Anonymity Properties of the Bitcoin P2P Network*: https://arxiv.org/abs/1703.08761
- Fanti et al.: *Dandelion++*: https://arxiv.org/abs/1805.11060 · BIP draft: https://github.com/gfanti/bips/blob/master/bip-dandelion.mediawiki
- Bitcoin Core private broadcast (Tor/I2P short-lived connections), PR #29415: https://github.com/bitcoin/bitcoin/pull/29415
- *SoK: Network-Level Attacks on the Bitcoin P2P Network*: https://repositori.upf.edu/server/api/core/bitstreams/8cc0b3c9-d076-4ba5-90d6-231c3b2ffc03/content
- Bitcoin P2P protocol reference: https://developer.bitcoin.org/reference/p2p_networking.html

### Clustering, change, peel chains, CoinJoin
- Meiklejohn et al.: *A Fistful of Bitcoins* (IMC 2013): https://cseweb.ucsd.edu/~smeiklejohn/files/imc13.pdf
- Kappos et al.: *How to Peel a Million* (USENIX Security 2022): https://arxiv.org/abs/2205.13882
- Müller et al.: *How Reliable Is the Multi-Input Heuristic … in Law Enforcement Contexts?* (2026): https://arxiv.org/abs/2607.07414
- Iknaio: *Address Clustering Is Not Evidence* (2026): https://iknaio.com/insights/address-clustering-issues/
- Stütz et al.: *Pinpointing and Measuring Wasabi and Samourai CoinJoins*: https://arxiv.org/abs/2109.10229
- CoinJoin detection heuristics (JoinMarket, Wasabi, Whirlpool): https://arxiv.org/abs/2311.12491
- Gavenda et al.: *Analysis of input-output mappings in coinjoin transactions* (2025): https://arxiv.org/abs/2510.17284
- crocs-muni coinjoin-analysis: https://github.com/crocs-muni/coinjoin-analysis
- CoinJoin detector rules discussion (payjoin tx-indexer): https://github.com/payjoin/tx-indexer/issues/5
- GraphSense (open-source crypto analytics): https://graphsense.org · paper: https://arxiv.org/abs/2102.13613 · https://github.com/graphsense/graphsense-lib

### Taint and risk propagation
- Tironsakkul et al.: *Probing the Bitcoin tainting methods* (LIFO/TIHO, profiling): https://arxiv.org/abs/1906.05754
- Anderson et al.: *Tendrils of Crime* (FIFO taint, diffusion of poison/haircut): https://arxiv.org/abs/1901.01769
- *TaintRank*: https://arxiv.org/abs/1907.01538
- *MPOCryptoML* (multi-source PPR for laundering patterns): https://arxiv.org/abs/2508.12641
- Tovanich & Cazabet: *Fingerprinting Bitcoin entities using money flow* (2023): https://link.springer.com/article/10.1007/s41109-023-00591-2

### ML datasets and benchmarks
- Weber et al.: *Anti-Money Laundering in Bitcoin* (Elliptic, KDD workshop 2019): https://arxiv.org/abs/1908.02591
- Elliptic dataset (Kaggle): https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
- Elmougy & Liu: *Elliptic++* (KDD 2023): https://arxiv.org/abs/2306.06108 · repo: https://github.com/git-disl/EllipticPlusPlus · data: https://drive.google.com/drive/folders/1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l
- Bellei et al.: *Elliptic2* (subgraph classification): https://arxiv.org/abs/2404.19109
- Trees vs GNNs on Elliptic++ (independent reproduction): https://github.com/BhaveshBytess/Revisiting-GNNs-FraudDetection

### Synthetic AML data (typologies we adapt)
- Altman et al.: *Realistic Synthetic Financial Transactions for AML* (AMLworld, NeurIPS 2023): https://arxiv.org/abs/2306.16424
- IBM AMLSim: https://github.com/IBM/AMLSim
- AMLGentex: https://github.com/aidotse/AMLGentex · paper: https://arxiv.org/abs/2506.13989

### Explainability
- Ying et al.: *GNNExplainer*: https://arxiv.org/abs/1903.03894
- LightGBM `predict(pred_contrib=True)` (TreeSHAP): https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.Booster.html
- SHAP: https://github.com/shap/shap
- XAI for crypto AML (GraphLIME / GNNExplainer): https://github.com/EktaU21/XAI_Cryptocurrency_Money_Laundering
- GNN + GraphLIME + LLM narratives (for contrast with our no-LLM choice): https://arxiv.org/abs/2506.14933

### Timing and geography
- Timezone classification from activity patterns (JSAI 2019): https://www.jstage.jst.go.jp/article/pjsai/JSAI2019/0/JSAI2019_1P2J1303/_pdf
- *Temporal and Geographical Analysis of Real Economic Activities in the Bitcoin Blockchain*: https://arxiv.org/abs/2307.08616
- *The Spatiotemporal Scaling Laws of Bitcoin Transactions* (IP↔address data): https://arxiv.org/abs/2309.11884

### Reference data (bundled offline)
- DB-IP Lite (CC BY 4.0): https://db-ip.com/db/lite.php · direct: `https://download.db-ip.com/free/dbip-country-lite-YYYY-MM.mmdb.gz`, `…/dbip-asn-lite-YYYY-MM.mmdb.gz` (CSV: `.csv.gz`)
- IPinfo Lite (optional, CC BY-SA 4.0): https://ipinfo.io/developers/ipinfo-lite-database
- MaxMind GeoLite (not used; EULA constraints): https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- IP2Location LITE ASN (alternative): https://lite.ip2location.com/database-ip-asn
- sapics/ip-location-db (mirrors, PDDL options): https://github.com/sapics/ip-location-db
- Tor bulk exit list: https://check.torproject.org/torbulkexitlist
- X4BNet VPN / datacenter lists: https://github.com/X4BNet/lists_vpn · raw: https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/vpn/ipv4.txt · https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/datacenter/ipv4.txt
- IP Knowledge Layer (alternative enrichment): https://github.com/ipanalytics/IP-Knowledge-Layer
- Natural Earth (public domain map data): https://www.naturalearthdata.com

### Interoperability
- MISP objects (`btc-wallet`, `btc-transaction`, `coin-address`): https://www.misp-project.org/objects.html · https://github.com/MISP/misp-objects
- misp-stix (MISP ↔ STIX): https://github.com/MISP/misp-stix

### Law
- BSA 2023, Section 63: https://indiacode.ecourtsindia.com/bsa/section/63.md
- BSA Schedule (certificate format with hash values): https://mynation.net/laws/bare-acts/bsa/bsa-sch.htm

### Deployment platforms (verified September 2026)
- Vercel functions limits: https://vercel.com/docs/functions/limitations · Hobby plan: https://vercel.com/docs/plans/hobby
- Render free tier: https://render.com/docs/free · pricing: https://render.com/pricing · compute plans: https://render.com/docs/compute-plans
- Render Blueprint spec: https://render.com/docs/blueprint-spec · prebuilt images: https://render.com/docs/deploying-an-image · deploy hooks: https://render.com/docs/deploy-hooks
- Railway pricing: https://railway.com/pricing
- Neon plans (if persistence is ever needed): https://neon.com/docs/introduction/plans
- Hugging Face Spaces (not used): https://huggingface.co/docs/hub/spaces-overview
- GitHub Container Registry: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- GitHub Student Developer Pack: https://education.github.com/pack

### Libraries and tools
**Python:**
- uv https://docs.astral.sh/uv/ · ruff https://docs.astral.sh/ruff/ · pyright https://github.com/microsoft/pyright · import-linter https://import-linter.readthedocs.io
- FastAPI https://fastapi.tiangolo.com · Pydantic https://docs.pydantic.dev · SQLAlchemy https://www.sqlalchemy.org · Alembic https://alembic.sqlalchemy.org
- DuckDB https://duckdb.org · Polars https://pola.rs · python-igraph https://python.igraph.org · SciPy https://scipy.org · NetworkX https://networkx.org
- LightGBM https://lightgbm.readthedocs.io · scikit-learn https://scikit-learn.org
- maxminddb https://github.com/maxmind/MaxMind-DB-Reader-python · defusedxml https://github.com/tiran/defusedxml · ijson https://github.com/ICRAR/ijson · orjson https://github.com/ijl/orjson
- Typer https://typer.tiangolo.com · sse-starlette https://github.com/sysid/sse-starlette · structlog https://www.structlog.org · prometheus_client https://github.com/prometheus/client_python
- argon2-cffi https://argon2-cffi.readthedocs.io · PyJWT https://pyjwt.readthedocs.io · WeasyPrint https://weasyprint.org
- pytest https://docs.pytest.org · Hypothesis https://hypothesis.readthedocs.io

**Web:**
- React https://react.dev · Vite https://vite.dev · TypeScript https://www.typescriptlang.org
- TanStack Query https://tanstack.com/query · TanStack Router https://tanstack.com/router · TanStack Table https://tanstack.com/table · TanStack Virtual https://tanstack.com/virtual
- Tailwind https://tailwindcss.com · shadcn/ui https://ui.shadcn.com · Radix https://www.radix-ui.com
- Cytoscape.js https://js.cytoscape.org · fcose https://github.com/iVis-at-Bilkent/cytoscape.js-fcose · Sigma.js https://www.sigmajs.org · graphology https://graphology.github.io
- deck.gl https://deck.gl · Apache ECharts https://echarts.apache.org · cmdk https://github.com/pacocoursey/cmdk · i18next https://www.i18next.com
- fetch-event-source https://github.com/Azure/fetch-event-source · Fontsource https://fontsource.org · IBM Plex https://github.com/IBM/plex · Zod https://zod.dev
- openapi-typescript https://openapi-ts.dev · Playwright https://playwright.dev · Vitest https://vitest.dev · pnpm https://pnpm.io · Astro Starlight https://starlight.astro.build

**Operations:**
- Caddy https://caddyserver.com · Docker Compose https://docs.docker.com/compose/
- Syft https://github.com/anchore/syft · Grype https://github.com/anchore/grype
- UptimeRobot https://uptimerobot.com

## 17.15 One paragraph, for pasting into a fresh AI session

> Build **Sutradhar**, an **offline-first** analyst platform for SIH 2026 PS **SIH26146** (NTRO): *AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic*.
>
> **What it does.** It ingests bulk **Bitcoin traffic metadata** (CSV/JSON/XML via versioned mapping profiles; fields: timestamp, src/dst IP and port, txid, input/output addresses and amounts, fee, script type, geo/ASN). It normalises money to **int64 satoshis** and time to **UTC microseconds**, and enriches IPs offline with **DB-IP Lite**, Tor and VPN/datacenter lists (with provenance). It builds a graph of IP / session / TX / address / entity / actor / sensor / ASN / country, where **every inferred edge carries an evidence envelope** (method, confidence, evidence refs, model version, run id).
>
> **The pipeline.** A deterministic 19-stage engine:
> - flows via **(address, amount) matching**;
> - `coinjoin_clf` **before** CIOH clustering, with a mega-cluster split;
> - `change_clf` and `peel_scorer`;
> - motif plugins;
> - sensor clock-skew and sessions;
> - **`origin_ranker`** (learned origin attribution with an explicit *not-observable* probability, beating first-spy);
> - noisy-OR IP→entity control and co-origin;
> - randomized-SVD embeddings;
> - `er_pair_clf` entity resolution with analyst assertions;
> - service and victim detection;
> - haircut taint with decay, service stop and PPR from watchlist seeds;
> - Isolation-Forest anomalies;
> - **`lead_ranker`** (LightGBM, isotonic-calibrated) producing ACTOR / CASHOUT / CHAIN / TX / IP leads with grades from independent evidence families (NET, FLOW, TAINT, ANOM, BEHAV), priority, hedged TreeSHAP reasons (`pred_contrib`), counterfactuals and ≤150-node evidence subgraphs;
> - an immutable per-run DuckDB file plus a manifest and **result digest** (reproducible).
>
> **Stack.** FastAPI modular monolith plus a worker (Postgres job queue with `SKIP LOCKED`; SQLite in demo). **Hash-chained append-only audit.** Evidence packs with a SHA-256 hash report (BSA 2023 s.63-aligned) and independent verification. React 19 + Vite + TanStack + Tailwind/shadcn + Cytoscape/Sigma/deck.gl/ECharts console with triage, canvas, dossiers and the **Wire ⇄ Ledger Replay**.
>
> **Synthetic world.** All data comes from an in-house generator (UTXO economy plus P2P diffusion propagation plus vantage/flow sensors plus adversary knobs plus ground truth, domain-randomised; the hero scenario is *Operation GHOSTLINE*).
>
> **Deployment.** One codebase, two targets. The **air-gapped docker-compose bundle** is the product (internal-only network plus an in-process offline guard; CI proves no egress). A **cloud showroom** runs the same images on Vercel (static) and Render Standard (API).
>
> **Hard rules:** no network calls, no LLMs, no Solana, no ground truth in the engine, no float money, no unhedged claims, no geographic-identity features. Every mutation is audited, every list is paginated, and every requirement has a test (`docs/requirements.csv`).

---

*End of blueprint. Where this document and reality disagree, this document is wrong and will be corrected, in the decision log.*
