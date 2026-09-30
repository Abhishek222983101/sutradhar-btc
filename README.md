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
| 4 | **AI/ML**: anomalies, clusters, ranked leads | Trained origin and change-address models, Isolation Forest, graph embeddings, evidence-ranked leads. | [`docs/EVAL.md`](docs/EVAL.md) |
| 5 | Parse all fields (timestamp, IPs, ports, TXID, addresses, amounts, fee, script type) | Exact integer satoshis, UTC microseconds, fee computed when absent, script type from address. | [`docs/data-contract.md`](docs/data-contract.md) |
| 6 | **Graph** linking IPs, wallets, transactions | Wallet clusters, value flows, origin and co-origin edges, each carrying its evidence. | `flow`, `origin`, `co_origin` tables |
| 7 | A **working model, not just rules** | Logistic origin model and change model trained on generated worlds and tested on unseen ones; Isolation Forest for anomalies. | `sutradhar evals train-origin` |
| 8 | **Ranked, explainable alerts with confidence** | Every lead has a score, a grade, plain reasons and a hedged summary. | Console → any lead |
| 9 | **Dashboard / link analysis** | Web console with leads, evidence, propagation replay, dataset X-ray, pipeline view. | [live demo](https://sutradhar-one-red.vercel.app) |
| 10 | Focus: **entity clustering** | Common-input ownership with a CoinJoin guard and a change-address model; graph embeddings; merge suggestions an analyst accepts or rejects. | [`e05_cluster.py`](packages/engine/sutradhar_engine/stages/e05_cluster.py) |
| 11 | Focus: **anomaly detection** | Isolation Forest over value, fee rate and split shape. | [`e08_anomaly.py`](packages/engine/sutradhar_engine/stages/e08_anomaly.py) |
| 12 | Focus: **peeling chains / mixing** | Timing-aware peel-chain traversal; CoinJoin detector. | [`e07_peel.py`](packages/engine/sutradhar_engine/stages/e07_peel.py), [`e04_coinjoin.py`](packages/engine/sutradhar_engine/stages/e04_coinjoin.py) |
| 13 | Focus: **risk propagation** from seed wallets | Value-weighted haircut taint from a watchlist, shown as evidence on leads. | [`e13_taint.py`](packages/engine/sutradhar_engine/stages/e13_taint.py) |
| 14 | **Synthetic dataset** modelled on real fields | UTXO economy, Bitcoin-style relay timing, sensors, ransomware, CoinJoin and darknet-market stories. | `sutradhar gen run` |
| 15 | Minimum dataset fields | Exactly the specified columns, plus optional extras. | [`docs/DATASET.md`](docs/DATASET.md) |
| 16 | **Open-source GeoIP** | DB-IP Lite (CC BY 4.0) bundled offline; source, licence, date and checksum recorded. | [`refdata/manifest.json`](packages/engine/sutradhar_engine/refdata/manifest.json) |
| 17 | Offline solution for **Linux** | `docker compose -f compose.airgap.yaml up` on any Linux host. | [`compose.airgap.yaml`](compose.airgap.yaml) |
| 18 | Working prototype, **code repo** | This repository, with CI, tests and a security gate. | [Actions](https://github.com/Abhishek222983101/sutradhar-btc/actions) |
| 19 | Short **technical write-up** | Approach, model choice, explainability method. | [`docs/TECHNICAL_WRITEUP.md`](docs/TECHNICAL_WRITEUP.md) |
| 20 | Dashboard with **evidence per flag** | Reasons, candidate IPs with probabilities, transactions, replay per lead. | Console → any lead |

---

## 🚀 Try it live: 30 seconds, no install

### **[👉 Open sutradhar-one-red.vercel.app](https://sutradhar-one-red.vercel.app)**

1. Click **Open the live demo**. You land on the console with a pre-analysed synthetic world.
2. Pick a lead. Read **why** it was flagged, see the **candidate IPs** with probabilities, and press **Replay** to watch
   the first announcements arrive at the sensors.
3. Open **What the engine did** to see every pipeline stage, its output and its timing.
4. **Try your own file**: upload a CSV, JSON, NDJSON or XML in the canonical layout and get leads back in seconds
   (uploads are deleted after 60 minutes).

---

## 📊 Results: the numbers, not just the claim

Every number is produced by a committed command against freshly generated worlds with hidden ground truth. Nothing is
hand-typed. Reproduce with `uv run sutradhar evals report` and read [`docs/EVAL.md`](docs/EVAL.md).

*Scenario `rich` (ransomware + CoinJoin coordinator + darknet market), 5 seeds, 1,421 observable transactions:*

| What | Result | Compared with |
|---|---|---|
| Origin IP found on the first try | **40.7%** (± 3.6%) | random guess **4.4%**, earliest-announcer rule **39.0%** |
| Origin IP within the top 3 | **53.0%** | |
| Best any method could do (true origin was heard at all) | 67.6% | ceiling |
| Wallet cluster purity vs. hidden truth | **99.9%** | |
| CoinJoin detection (precision / recall) | **100% / 100%** | 30 mixes |
| Change output identified per transaction | **94.0%** | |
| Peel-chain hops (precision / recall) | 81.6% / 100% | |
| Merge suggestions that are truly one operator | **37.6%** | random pairs 0.76% |

**Read this honestly.** The learned origin model beats the earliest-announcer rule by under two points; both sit near the
ceiling that the sensor placement allows. The gains come from putting evidence, clustering and explanations around the
origin call, not from a magic origin model. CoinJoin results are on our own generator's clean mixes, so real-world recall
will be lower. Scores are transparent evidence scores, not calibrated probabilities. See the limits in
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
packages/engine     ingest + the analysis stages E01–E19 + trained model weights + bundled GeoIP
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
| [**DATASET.md**](docs/DATASET.md) | The dataset fields and the three generated scenarios |
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
