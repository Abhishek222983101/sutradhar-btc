<div align="center">

# 🧵 Sutradhar
### Offline AI for Bitcoin Transaction Traffic: find the IP behind the wallet

**Given network sightings and blockchain data, Sutradhar tells an investigator which IP most likely broadcast a transaction, which wallets are one operator, and why, with the evidence for every claim.**

[![Live Demo](https://img.shields.io/badge/🔴_LIVE_DEMO-sutradhar--one--red.vercel.app-2ea44f?style=for-the-badge)](https://sutradhar-one-red.vercel.app)
[![Live API](https://img.shields.io/badge/⚙️_LIVE_API-onrender.com-blue?style=for-the-badge)](https://sutradhar-btc-api.onrender.com/api/docs)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![CI](https://img.shields.io/github/actions/workflow/status/Abhishek222983101/sutradhar-btc/ci.yml?branch=main&label=CI)](https://github.com/Abhishek222983101/sutradhar-btc/actions)
[![Offline](https://img.shields.io/badge/offline-proved_with_--network_none-brightgreen)](#-proved-offline)

</div>

---

## 🧑‍⚖️ Judge quick start

1. Open **https://sutradhar-one-red.vercel.app** and press **Start the 8-minute tour**, or go straight to `#/guide`
   (the **Judge guide**): numbered steps with the exact text to paste, what you should see, and which requirement each
   step proves. A small tour card follows you through the site.
2. The 20 requirements are listed on the landing page, each linked to a live page that proves it.
3. The demo server is on a free tier. After an idle spell it can take about 45 seconds to wake; the header shows
   "Waking server" and every page continues on its own.
4. To run it yourself with no internet, see [Run it yourself](#-run-it-yourself) (one `uv sync`, one `selftest`).

Pages: **Console** (leads with tabs Summary, Why, What-if, Evidence, Network, Path to seed, Timeline, Members; search;
upload your own file, with sample CSV/JSON/XML to download), **Cases** (notes and four exports), **Verify** (sealed
evidence packs: per-file SHA-256 plus an HMAC seal), **Govern** (models, settings, audit chain), **System** (air-gap
proof), **How it works**, **Academy**, **Scenario Studio**.

---

## 📋 At a glance

| | |
|---|---|
| **Problem Statement** | PS 26146: *AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic* |
| **Organisation** | National Technical Research Organisation (NTRO) |
| **Theme / Category** | Blockchain & Cybersecurity / Software |
| **Dataset** | Synthetic, generated in-house (the PS provides none). Hidden ground truth is used only for evaluation. |
| **Team** | Team Paradigm |
| **Live demo** | **https://sutradhar-one-red.vercel.app** ← open this first |
| **Live API + docs** | https://sutradhar-btc-api.onrender.com/api/docs |

> ⏱ The demo API runs on a free tier and sleeps when idle. The first request after a pause can take about a minute.

---

## 💡 The idea, in 20 seconds

Bitcoin addresses are pseudonymous, but the network is not. The node that first announces a transaction leaves a timing
trace at any listening sensor, and the same wallet keeps being announced from the same place. Sutradhar joins the two
worlds: **network sightings** (who announced what, when) and **ledger data** (which addresses moved which coins). It
scores every candidate origin IP, groups addresses into wallets, and turns the overlap into a **ranked list of leads**,
each with a score, plain-language reasons and the transactions behind it.

## 🎯 What the problem statement asked for

> Design and build a complete system **(offline)** that ingests bulk Bitcoin transaction/network metadata (CSV/JSON/XML),
> correlates network-layer observations with blockchain-layer data, and applies AI/ML to detect anomalies, cluster
> entities, and generate prioritized, explainable investigative leads. *(paraphrased from PS 26146)*

---

## ✅ Every requirement, and where to check it

| # | PS asked for | What we built | Proof |
|---|---|---|---|
| 1 | Complete **offline** system | Runs with no network. The selftest passes inside `docker run --network none`, and the compose stack's API has no route to the internet. | CI job `offline`, [`compose.airgap.yaml`](compose.airgap.yaml) |
| 2 | Ingest **CSV / JSON / XML** | CSV, TSV, JSON, NDJSON and XML give byte-identical normalised data; XML entity attacks are blocked; an auto-mapper handles renamed columns; a rejects report says what was refused and why. | [`test_formats.py`](packages/engine/tests/test_formats.py), [`automap.py`](packages/engine/sutradhar_engine/ingest/automap.py) |
| 3 | **Correlate** network with blockchain | Origin-IP model over sensor timing, joined to wallet clusters. | [`e09_origin.py`](packages/engine/sutradhar_engine/stages/e09_origin.py), [`e17_rank.py`](packages/engine/sutradhar_engine/stages/e17_rank.py) |
| 4 | **AI/ML**: anomalies, clusters, ranked leads | Trained origin, change-address and CoinJoin models, a calibrated LightGBM lead ranker, Isolation Forest, graph embeddings, evidence-ranked leads. | [`docs/EVAL.md`](docs/EVAL.md) |
| 5 | Parse all fields (timestamp, IPs, ports, TXID, addresses, amounts, fee, script type) | Exact integer satoshis, UTC microseconds, fee computed when absent, script type from address. | [`docs/data-contract.md`](docs/data-contract.md) |
| 6 | **Graph** linking IPs, wallets, transactions | Wallet clusters, value flows, origin and co-origin edges, each carrying its evidence. | `flow`, `origin`, `co_origin` tables |
| 7 | A **working model, not just rules** | Logistic origin, change-address and CoinJoin classifiers trained on generated worlds and tested on unseen ones; LightGBM lead ranker; Isolation Forest for anomalies. | `sutradhar evals train-origin`, `train-coinjoin` |
| 8 | **Ranked, explainable alerts with confidence** | Every lead has a score (calibrated for wallet, cash-out and IP leads), a grade, TreeSHAP reasons, the evidence against it, a what-if and a hedged summary. | Console → any lead |
| 9 | **Dashboard / link analysis** | Web console with leads, tabbed evidence, link graph, Sankey flows, propagation replay, dataset X-ray, pipeline view. | [live demo](https://sutradhar-one-red.vercel.app) |
| 10 | Focus: **entity clustering** | Common-input ownership with a CoinJoin guard and a change-address model; graph embeddings; merge suggestions an analyst accepts or rejects. | [`e05_cluster.py`](packages/engine/sutradhar_engine/stages/e05_cluster.py) |
| 11 | Focus: **anomaly detection** | Isolation Forest over value, fee rate and split shape. | [`e08_anomaly.py`](packages/engine/sutradhar_engine/stages/e08_anomaly.py) |
| 12 | Focus: **peeling chains / mixing** | Timing-aware peel-chain traversal and a lead scorer; trained CoinJoin classifier (`coinjoin-lr@1`). | [`e07_peel.py`](packages/engine/sutradhar_engine/stages/e07_peel.py), [`e04_coinjoin.py`](packages/engine/sutradhar_engine/stages/e04_coinjoin.py) |
| 13 | Focus: **risk propagation** from seed wallets | Value-weighted haircut taint with hop decay and service stopping, personalised PageRank and k-best paths from a watchlist, shown as the Path to seed tab. | [`e13_taint.py`](packages/engine/sutradhar_engine/stages/e13_taint.py) |
| 14 | **Synthetic dataset** modelled on real fields | UTXO economy, Bitcoin-style relay timing, sensors, ransomware, CoinJoin and darknet-market stories. | `sutradhar gen run` |
| 15 | Minimum dataset fields | Exactly the specified columns, plus optional extras. | [`docs/DATASET.md`](docs/DATASET.md) |
| 16 | **Open-source GeoIP** | DB-IP Lite (CC BY 4.0) bundled offline; source, licence, date and checksum recorded. | [`refdata/manifest.json`](packages/engine/sutradhar_engine/refdata/manifest.json) |
| 17 | Offline solution for **Linux** | `docker compose -f compose.airgap.yaml up` on any Linux host. | [`compose.airgap.yaml`](compose.airgap.yaml) |
| 18 | Working prototype, **code repo** | This repository, with CI, tests and a security gate. | [Actions](https://github.com/Abhishek222983101/sutradhar-btc/actions) |
| 19 | Short **technical write-up** | Approach, model choice, explainability method. | [`docs/TECHNICAL_WRITEUP.md`](docs/TECHNICAL_WRITEUP.md) |
| 20 | Dashboard with **evidence per flag** | Reasons, candidate IPs with probabilities, transactions, replay per lead, and a sealed (hash + HMAC) evidence pack per case. | Console → any lead |

---

## 🚀 Try it live: 30 seconds, no install

### **[👉 Open sutradhar-one-red.vercel.app](https://sutradhar-one-red.vercel.app)**

1. Click **Open the console** (or **Start the 8-minute tour**). You land on the console with a pre-analysed synthetic world.
2. Pick a lead. Read **why** it was flagged, see the **candidate IPs** with probabilities, and press **Replay** to watch
   the first announcements arrive at the sensors.
3. Open **What the engine did** to see every pipeline stage, its output and its timing.
4. **Try your own file**: upload a CSV, JSON, NDJSON or XML in the canonical layout and get leads back in seconds
   (uploads are deleted after 60 minutes).

---

## 📊 Results: the numbers, not just the claim

Every number is produced by a committed command against freshly generated worlds with hidden ground truth. Nothing is
hand-typed. Reproduce with `uv run sutradhar evals report` and read [`docs/EVAL.md`](docs/EVAL.md).

*Scenario `rich` (ransomware + CoinJoin coordinator + darknet market), 5 seeds, 2,038 observable transactions:*

| What | Result | Compared with |
|---|---|---|
| Origin IP found on the first try | **39.1%** (± 3.4%) | random guess **4.4%**, earliest-announcer rule **37.5%** |
| Origin IP within the top 3 | **51.5%** | |
| Best any method could do (true origin was heard at all) | 67.8% | ceiling |
| Wallet cluster purity vs. hidden truth | **99.9%** | 99.5% if CoinJoins were merged |
| CoinJoin classifier, trained (precision / recall) | **100% / 100%** | 30 mixes; the heuristic it replaced also scores 100% / 100% |
| Change output identified per transaction | **95.2%** | |
| Peel-chain hops (precision / recall) | 37.1% / 100% | published CHAIN leads that are real chains: 100% |
| Lead ranker PR-AUC (with / without watchlist seeds) | **0.983 / 0.980** | taint alone: 0.963 / 0.013 |
| Calibration error (ECE) | **0.002** | |
| Merge suggestions that are truly one operator | **34.0%** | random pairs 0.69% |

**Read this honestly.** The learned origin model beats the earliest-announcer rule by under two points (39.1% vs 37.5%); both sit near the
ceiling that the sensor placement allows. The gains come from putting evidence, clustering and explanations around the
origin call, not from a magic origin model. CoinJoin results are on our own generator's clean mixes, so real-world recall
will be lower. Wallet, cash-out and IP leads use the isotonic-calibrated LightGBM ranker; peeling-chain and unusual-transaction leads are scored by readable rules and labelled as such. See the limits in
[`docs/TECHNICAL_WRITEUP.md`](docs/TECHNICAL_WRITEUP.md#limits).

---

## 🏗️ How it works

```
 traffic (CSV/JSON/XML)                                    ┌───────────────────────────────┐
        │                                                  │ E02 GeoIP   E04 CoinJoin      │
        ▼                                                  │ E06 change  E05 wallet cluster│
 ingest ─► validate ─► normalise ─► dataset store ─► run ─►│ E03 flows   E12 embeddings    │─► leads
 (rejects report,      (exact sats,   (immutable,          │ E07 peel    E08 anomalies     │   (score, grade,
  auto-mapper)          UTC micros)    hashed)             │ E09 origin  E11 co-origin     │    reasons,
                                                           │ E13 taint   E14 fingerprints  │    evidence)
                                                           │ E15 motifs  E16 suggestions   │
                                                           │ E17 rank    E18 explain       │
                                                           └───────────────────────────────┘
```

* **Two immutable stores.** A dataset never changes after ingest; a finished run is read-only. The same input gives the
  same result digest, checked in the selftest.
* **Every derived claim carries its evidence** (method, confidence, the transactions behind it).
* **Plugins.** Extra stages can be added by any Python package. See [`docs/PLUGINS.md`](docs/PLUGINS.md).
* **Tamper-evident audit log.** Every state change is hash-chained; `sutradhar audit verify` recomputes the chain.

## 🔒 Proved offline

```bash
docker build -f deploy/api.Dockerfile -t sutradhar .
docker run --rm --network none sutradhar sutradhar selftest      # generate → ingest → analyse → verify, no network
```

CI runs exactly this on every push. The compose stack goes further: the API sits on an `internal` network with no route
out, so even a compromised process could not phone home.

## 💻 Run it yourself

```bash
git clone https://github.com/Abhishek222983101/sutradhar-btc.git && cd sutradhar-btc
uv sync                                              # Python 3.12 workspace
uv run sutradhar gen run --scenario rich --seed 1 --out worlds/rich     # a synthetic world
uv run sutradhar ingest worlds/rich/data/traffic.csv --out data/datasets --dataset-id ds_demo
uv run sutradhar run data/datasets/ds_demo --out data/runs --run-id run_demo
uv run sutradhar selftest                            # 8 end-to-end checks
uv run sutradhar evals report                        # reproduce every number above
```

**The full offline product (web + API + worker):**

```bash
export JWT_SECRET=$(openssl rand -hex 32)
docker compose -f compose.airgap.yaml up -d --build
docker compose -f compose.airgap.yaml exec api sutradhar users create --email you@example.org --name You --role lead
# open http://127.0.0.1:8080 and sign in
```

**Your own data.** Files in the canonical layout load directly. Files with other column names:
`uv run sutradhar ingest yourfile.csv --auto-map` proposes and applies a mapping, printing every guess.

## 📁 Project structure

```
packages/schemas    the data contract: fields, units, evidence envelope (imports nothing internal)
packages/engine     ingest + the analysis stages E01–E22 + trained model weights + bundled GeoIP
packages/generator  synthetic Bitcoin worlds with hidden ground truth
packages/evals      training and evaluation against ground truth (the only code that reads truth)
packages/cli        the `sutradhar` command
apps/api            FastAPI service: auth, audit log, job queue, SSE progress, offline guard
apps/web            the console and judge landing page (React)
deploy/             Dockerfiles and Caddyfile
docs/               write-up, evaluation, data contract, invariants, decisions
```

Module boundaries are enforced in CI: the engine can never import the generator or the evaluation code, so the system
under test cannot see ground truth.

## 📚 Documentation

| Doc | What's in it |
|---|---|
| [**TECHNICAL_WRITEUP.md**](docs/TECHNICAL_WRITEUP.md) | Approach, model choice, explainability method, limits |
| [**EVAL.md**](docs/EVAL.md) | Every metric, per-seed, reproducible |
| [**DATASET.md**](docs/DATASET.md) | The dataset fields and the generated scenarios |
| [**PLUGINS.md**](docs/PLUGINS.md) | Writing your own analysis stage |
| [**data-contract.md**](docs/data-contract.md) | Field-level contract and JSON Schemas |
| [**INVARIANTS.md**](docs/INVARIANTS.md) | The 20 rules every change must keep, each with its test |

## 🛠️ Tech stack

`Python 3.12` `DuckDB` `Polars` `scikit-learn` `SciPy` `FastAPI` `SQLAlchemy` `React 19` `Vite` `Docker` `Caddy` · deployed on `Vercel` (site) + `Render` (live API)

---

## 👥 Team Paradigm

Built end-to-end for **Smart India Hackathon 2026 · PS 26146**.

## 📄 License and attributions

Apache 2.0 (see [`LICENSE`](LICENSE)). IP geolocation data: **DB-IP Lite**, CC BY 4.0, https://db-ip.com. All Bitcoin data in
this repository is synthetic; no real traffic or seized data is included.
