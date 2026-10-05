# Technical write-up: approach, model choice and explainability

Problem statement SIH26146 (NTRO): an offline system that ingests Bitcoin transaction and network metadata, correlates
the two layers, applies AI/ML, and produces prioritised, explainable leads. This note covers the approach, why each
model was chosen, how explanations are produced, and where the system is weak. Every number here comes from
[`EVAL.md`](EVAL.md) and can be regenerated with `uv run sutradhar evals report`.

## 1. Approach

The two layers describe the same events from different sides.

* **Network layer** (timestamp, source IP and port, destination IP and port, txid): a listening sensor logs which peer
  announced a transaction and when. The first announcer is often, not always, the origin.
* **Ledger layer** (txid, input and output addresses and amounts): shows which addresses moved which coins.

The join key is the txid. For each transaction Sutradhar (1) scores every announcing IP as a possible origin, (2) groups
addresses into wallets, and (3) links an IP to a wallet when the IP keeps being the likely origin of that wallet's
spends. Around that core it adds anomaly detection, peeling-chain and CoinJoin detection, risk propagation from seed
wallets, and merge suggestions. All of it feeds one ranked lead list.

The pipeline is a fixed sequence of stages (E01 to E22) over an immutable dataset store. Each stage declares the tables
it reads and writes, so the run is inspectable and a stage that breaks its contract fails the run. The same input
produces the same result digest; this is checked in the selftest.

## 2. Data

The PS provides no dataset, so we built a generator (`packages/generator`): a UTXO ledger with exact value
conservation, exchanges, ordinary users, a ransomware operation (victim payments, consolidation, peeling chain,
cash-out), a Whirlpool-style CoinJoin coordinator, and a darknet market. Every transaction is propagated through a
simulated peer-to-peer network using Bitcoin Core's diffusion delays, and sensors record the first announcers. IPs come
from per-country blocks of the open DB-IP database so GeoIP enrichment has real answers. Ground truth (true origin,
wallet ownership, change outputs, peel hops) is written to separate files that only the evaluation package may read.

## 3. Models and why

| Task | Model | Why this and not something heavier |
|---|---|---|
| Origin IP per transaction | Logistic regression over eight per-candidate timing features (delay from the first sighting, exponential decay, rank, sensors that heard it, number of candidates, how often this IP is first elsewhere, its volume) | Linear weights are readable, train in seconds, and cannot overfit a small world the way a deep model would. The weights are a JSON file. |
| Change-address identification | Logistic regression over address freshness, script match, value rank, share of input, roundness, position | Same reasons. 95.2% of transactions get the true change output ranked first. |
| Anomalous transactions | Isolation Forest (200 trees, seeded) over log value, inputs, outputs, fee rate, output spread | Unsupervised, needs no labels, works on any dataset. |
| Wallet clustering | Common-input ownership by union-find, with CoinJoin transactions excluded and confident change outputs linked | A published, well understood heuristic. The guard matters: merging CoinJoin inputs joins strangers. |
| CoinJoin detection | Logistic regression (`coinjoin-lr@1`) over twelve structural features of a transaction: input and output counts, how many outputs share one value, equal-output share, distinct input addresses, script homogeneity, output value spread, roundness | A mix has a recognisable shape, and the model learns where the boundary sits instead of us hand-setting thresholds. The earlier scored heuristic stays as the baseline it is evaluated against and as a fallback if weights are missing. |
| Peeling chains | Traversal: one input, two outputs, large remainder, next hop within an hour | Real peeling is automated and fast; without the timing rule hop precision was 7%, with it about 37% (recall stays 100%), and 100% of the published chain leads are real chains. |
| Risk propagation | Value-weighted haircut taint from watchlisted seeds, with hop decay, service stopping, personalised PageRank and k-best paths | Risk thins as funds mix with clean money, and the path is the explanation. |
| Lead ranking | LightGBM over 36 actor features, isotonic-calibrated (ECE 0.002); TreeSHAP reasons and counterfactuals | Calibrated confidence for wallet, cash-out and IP leads; PR-AUC 0.983 with watchlist seeds, 0.980 without. |
| Entity relationships | Truncated SVD of the wallet flow graph (16 dimensions), co-origin (shared IP) and behavioural fingerprints combine into merge suggestions | Cheap, deterministic, and every suggestion lists its reasons. |

There is deliberately no deep model and no language model. On worlds this size they would memorise the generator, and
they cannot show their working.

**Training and testing are separate.** The origin model trains on seeds 100 to 119 (a mix of two scenarios) and is
evaluated on seeds 1 to 5, which it has never seen. The change model trains on seeds 200 to 215. The lead ranker
trains on seeds 300 to 341, cycling through three scenarios (including `hard`, which adds benign look-alike
actors — merchants, payroll, trading bots — as hard negatives) and is evaluated on the same unseen 1-to-5 range,
both with and without watchlist seeds present. The CoinJoin classifier trains on 60 domain-randomised worlds (seeds 400
to 459: varied coordinator denominations, participant counts and cadence, plus mining pools, payroll, merchants,
traders and gambling sites as hard negatives), is validated on 12 more worlds split by world, never by row (seeds 460 to
471), and is reported on seeds 1 to 5 and on two further stress worlds (600, 601).

## 4. Results, and what they mean

On the `rich` scenario, five unseen worlds, 2,038 observable transactions:

* **Origin IP first try: 39.1%**, top three: 51.5%. Random guessing among announcers gets 4.4%. The simple rule "the
  earliest announcer is the origin" gets 37.5%.
* The true origin announced to a sensor in only **67.8%** of cases. That is the ceiling for any method, because
  when the origin never appears in the log there is nothing to find.
* So the trained model is only modestly better than the classic rule (about 1.6 points), and both sit well below the
  ceiling that the sensor placement allows. We report this rather than hide it.
* Wallet clusters are 99.9% pure (99.5% if CoinJoins were merged, which is why the guard exists). Change outputs are
  identified for 95.2% of transactions; the change links used for clustering are 99.6% precise (1,317 links at a strict
  threshold; a looser threshold added links but lowered purity).
* Lead ranker: PR-AUC 0.983 with watchlist seeds and 0.980 without (taint alone: 0.963 with, 0.013 without); the
  true illicit actors are ranked first 98.2% / 96.5% of the time; calibration error 0.002.
* CoinJoin: the trained classifier finds 30 of 30 mixes with no false alarms on the evaluation worlds, and 175 of 175
  on its held-out validation worlds. The scored heuristic it replaced scores the same (100% / 100%), so the model
  matches that baseline rather than beating it: the generator's look-alikes (pool payouts, merchant payouts, payroll)
  never carry equal-valued outputs, so they are easy negatives. What the trained model adds is a learned boundary and
  graded probabilities instead of hand-set gates. These are still our own generator's mixes.

## 5. Explainability

Each lead is stored with structured **reasons**. A reason has a family (network, flow, taint, anomaly), a named feature,
its value and its contribution, and a plain sentence. Examples: "This IP was the most likely first sender for 4
transactions spent by this wallet cluster", "About 41% of this cluster's value traces back to a watchlisted wallet".

* **Linear models** make attribution direct: a feature's contribution is its weight times its standardised value.
* **The Isolation Forest** reports "more unusual than X% of the dataset" (rank-normalised), which is honest about what the
  model knows.
* **Evidence is traceable.** A lead links to its transactions; for each, the candidate IPs with probabilities and the raw
  sensor arrivals (the propagation replay), so an analyst can check the claim against the data.
* **Wording is hedged.** Summaries say "evidence suggests" and "lead for review", never that someone is guilty.
* **Analysts decide.** Merge suggestions are never applied automatically. A lead analyst accepts or rejects each one with
  a reason, and the decision goes into the tamper-evident audit log.

## 6. Offline and security

The API and worker install an outbound-connection guard (name resolution and public addresses are refused). The job
process runs in its own interpreter with no database URL or secrets. XML is parsed with entity and DTD loading disabled.
The compose stack puts the API on a network with no route to the internet. CI runs the whole pipeline inside
`docker run --network none`. Passwords use argon2id; refresh tokens rotate and reuse revokes the session.

## 7. Limits

* **Synthetic data only.** We generated the world, so results say how the method behaves under our model of Bitcoin's
  network, not how it performs on real captures. Real traffic brings Tor and VPN exits, NAT, partial sensor coverage
  and messier wallets.
* **Sensor model.** The origin model is trained on a few listening sensors that log the first announcers. The generator
  can also produce flow-record, mixed and single-record data and the X-ray detects which one a dataset is, but we have not
  trained or evaluated the origin model on anything other than the sensor model.
* **Calibration is isotonic, not conformal.** ACTOR/CASHOUT/IP leads use the trained, isotonic-calibrated ranker
  (ECE 0.002 on held-out data); CHAIN and TX leads still use a transparent rule-based score, which the interface
  labels as such rather than presenting it as a probability.
* **Clean CoinJoins.** The classifier is trained and tested on generated mixes (one denomination per coordinator, no
  remixes), and matches its heuristic baseline there. The generator has no equal-valued benign look-alikes, so that
  hard case is untested; real mixes vary and recall will be lower.
* **Small worlds.** Hundreds of transactions, not millions. The engine is columnar and streaming, but we have not
  benchmarked at production scale.
* **Peel-chain hops.** Hop-level precision is 37.1%, so many individual hops the traversal walks are not part of a real
  chain; the published CHAIN leads, which need several consecutive hops, were 100% real chains on our worlds.

## 8. Also shipped

* **Tamper-evident evidence packs.** Every file in an exported pack is hashed (SHA-256) into `manifest.json`, and the
  manifest carries an HMAC-SHA256 seal from the issuing server, so editing a file or editing the manifest to match
  both fail verification (Verify page, `POST /api/v1/verify`).
* **Generator tooling.** `sutradhar gen run --format csv|json|ndjson|xml` (all four ingest to identical content);
  four observation models (vantage, flow, mixed, single); `gen randomize` for domain-randomised worlds; and
  `gen validate`, a realism report against target bands that flags, rather than hides, out-of-range checks.
* **Reference data.** A hook matches IPs against Tor-exit and public-VPN ranges. The list ships empty by design (the
  product never downloads anything); a maintainer fills it with `scripts/fetch_anon_ranges.py`.
* **Judge guide.** The web app has a guided tour, a system page proving the offline guard, and a "how it works" page
  that reads the live API for models and evaluation.
