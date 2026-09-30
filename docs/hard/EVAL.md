# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `hard`, seeds [1, 2, 3]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **40.8%** (± 2.1% across seeds) |
| Origin IP in top 3 candidates | **53.0%** |
| Ceiling: true origin announced to a sensor at all | 69.2% |
| Baseline: earliest announcer wins ("first-spy") | 39.7% |
| Baseline: random guess among announcers | 4.3% |
| Wallet cluster purity vs. hidden truth | **99.9%** |
| Observable transactions evaluated | 1364 |
| CoinJoin detection precision / recall | **100.0%** / **100.0%** (18 CoinJoins) |
| Cluster purity if CoinJoins were merged (ablation) | 99.6% |
| Peel-chain hops: precision / recall | 0.0% / 0.0% (published CHAIN leads that are real chains: 100.0%) |
| Merge suggestions (top 50): same operator | 6.7% (random pairs: 0.64%) |
| Lead ranker PR-AUC, with watchlist seeds / without | **0.972** / **0.851** |
| Baseline: taint alone, PR-AUC with seeds / without | 1.000 / 0.011 |
| Illicit actors ranked first (R-precision), with seeds / without | 97.0% / 85.6% (illicit share of actors: 1.1%) |
| Illicit actors found in the top 20, with seeds / without | 100.0% / 88.6% |
| Calibration error (ECE), with / without seeds | 0.001 / 0.002 |
| Stability: PR-AUC change when the country feature is removed | +0.0000 |
| Change output identified (per transaction) | **95.3%** |
| Change links used for clustering: precision | **99.6%** (1385 links) |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 40.9% | 54.5% | 4.3% | 1102 | 99.9% |
| 2 | 43.3% | 55.5% | 4.3% | 1127 | 99.8% |
| 3 | 38.3% | 49.0% | 4.3% | 1136 | 99.8% |
