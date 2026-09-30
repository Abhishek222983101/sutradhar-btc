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

The pipeline is a fixed sequence of stages (E01 to E19) over an immutable dataset store. Each stage declares the tables
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
| Change-address identification | Logistic regression over address freshness, script match, value rank, share of input, roundness, position | Same reasons. 94% of transactions get the true change output ranked first. |
| Anomalous transactions | Isolation Forest (200 trees, seeded) over log value, inputs, outputs, fee rate, output spread | Unsupervised, needs no labels, works on any dataset. |
| Wallet clustering | Common-input ownership by union-find, with CoinJoin transactions excluded and confident change outputs linked | A published, well understood heuristic. The guard matters: merging CoinJoin inputs joins strangers. |
| CoinJoin detection | Score from equal-output count, input count and equal-output share | Equal-value outputs are the defining property of a mix. |
| Peeling chains | Traversal: one input, two outputs, large remainder, next hop within an hour | Real peeling is automated and fast; without the timing rule precision was 7%, with it 82%. |
| Risk propagation | Value-weighted haircut taint from watchlisted seeds | Risk thins as funds mix with clean money. |
| Entity relationships | Truncated SVD of the wallet flow graph (16 dimensions), co-origin (shared IP) and behavioural fingerprints combine into merge suggestions | Cheap, deterministic, and every suggestion lists its reasons. |

There is deliberately no deep model and no language model. On worlds this size they would memorise the generator, and
they cannot show their working.

**Training and testing are separate.** The origin model trains on seeds 100 to 119 (a mix of two scenarios) and is
evaluated on seeds 1 to 5, which it has never seen. The change model trains on seeds 200 to 215.

## 4. Results, and what they mean

On the `rich` scenario, five unseen worlds, 1,421 observable transactions:

* **Origin IP first try: 40.7%**, top three: 53.0%. Random guessing among announcers gets 4.4%. The simple rule "the
  earliest announcer is the origin" gets 39.0%.
* The true origin announced to a sensor in only **67.6%** of cases. That is the ceiling for any method, because
  when the origin never appears in the log there is nothing to find.
* So the trained model is only modestly better than the classic rule (under two points), and both are within a few points
  of the ceiling. We report this rather than hide it.
* Wallet clusters are 99.9% pure. Change links used for clustering are 99.2% precise (260 links at a strict threshold;
  a looser threshold added links but lowered purity, so we chose the strict one).
* CoinJoin: 30 of 30 found, no false alarms, on our own clean mixes.

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
* **Sensor model.** We assume a few listening sensors that log the first announcers. Flow-record style data (ISP-level
  captures) uses a different observation model that is detected but not yet exploited.
* **Scores are not calibrated probabilities.** They are transparent evidence scores; the interface says so.
* **Clean CoinJoins.** Real mixes vary (multiple denominations, remixes); recall will be lower.
* **Small worlds.** Hundreds of transactions, not millions. The engine is columnar and streaming, but we have not
  benchmarked at production scale.
* **Peel-chain false positives.** 82% precision means about one in five flagged hops is not part of a real chain.
