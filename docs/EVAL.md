# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `rich`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **39.1%** (± 3.4% across seeds) |
| Origin IP in top 3 candidates | **51.5%** |
| Ceiling: true origin announced to a sensor at all | 67.8% |
| Baseline: earliest announcer wins ("first-spy") | 37.5% |
| Baseline: random guess among announcers | 4.4% |
| Wallet cluster purity vs. hidden truth | **99.9%** |
| Observable transactions evaluated | 2038 |
| CoinJoin detection precision / recall | **100.0%** / **100.0%** (30 CoinJoins) |
| Cluster purity if CoinJoins were merged (ablation) | 99.5% |
| Peel-chain hops: precision / recall | 37.1% / 100.0% (published CHAIN leads that are real chains: 100.0%) |
| Merge suggestions (top 50): same operator | 34.0% (random pairs: 0.69%) |
| Lead ranker PR-AUC, with watchlist seeds / without | **0.983** / **0.980** |
| Baseline: taint alone, PR-AUC with seeds / without | 0.963 / 0.013 |
| Illicit actors ranked first (R-precision), with seeds / without | 98.2% / 96.5% (illicit share of actors: 1.3%) |
| Illicit actors found in the top 20, with seeds / without | 100.0% / 100.0% |
| Calibration error (ECE), with / without seeds | 0.002 / 0.002 |
| Stability: PR-AUC change when the country feature is removed | +0.0000 |
| Change output identified (per transaction) | **95.2%** |
| Change links used for clustering: precision | **99.6%** (1317 links) |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 41.9% | 57.0% | 4.4% | 906 | 100.0% |
| 2 | 42.5% | 55.0% | 4.5% | 898 | 99.7% |
| 3 | 40.5% | 53.4% | 4.3% | 929 | 99.9% |
| 4 | 37.3% | 47.2% | 4.3% | 902 | 99.9% |
| 5 | 33.4% | 44.9% | 4.4% | 943 | 99.9% |
