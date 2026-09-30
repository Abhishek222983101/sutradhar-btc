# Pitch outline (SIH format)

**Problem.** NTRO needs an offline system that ingests Bitcoin transaction+network metadata, correlates the
network layer (who broadcast what, when) with the ledger layer (who paid whom), and surfaces ranked, explainable
leads with AI/ML — not just rules.

**Approach.** A modular pipeline (E01–E22): ingest any of CSV/JSON/XML → normalise → GeoIP-enrich → detect
CoinJoins → cluster wallets (common-input-ownership + a trained change-address model) → score origin IPs per
transaction (trained logistic model) → propagate risk from watchlisted seeds (haircut taint + personalized
PageRank) → a trained LightGBM ranker turns ~36 actor features into calibrated, graded, explained leads.

**Architecture.** One diagram: ingest → dataset store (immutable) → engine stages → run store (immutable) →
API (audit-chained, offline-guarded) → console. Everything reproducible: same input gives the same result digest.

**Live demo.** Open the console, pick a top ACTOR lead, show Why → Against this reading → What would clear this
→ Investigate graph → Replay. Upload a fresh file live. Show `sutradhar selftest` passing with `--network none`.

**Numbers (from the metrics page, not the deck).** Origin IP top-1 39.1% vs 4.4% random baseline vs 67.8%
ceiling; lead ranker PR-AUC 0.983; CoinJoin detection 100%/100% on generated mixes; change-address ID 95.2%.
Every number is reproducible with one command against fresh, unseen synthetic worlds.

**Security & lawful use.** Argon2id, hash-chained audit log, offline guard proven at the network level, RBAC
tested per-route, synthetic data only — nothing here ever touches real seized data.

**Impact.** A single investigator can go from a raw traffic dump to a ranked, evidence-backed lead list — with
the evidence a court can actually inspect — in minutes, entirely air-gapped.
