# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `demo`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **38.9%** (± 5.3% across seeds) |
| Origin IP in top 3 candidates | **51.3%** |
| Ceiling: true origin announced to a sensor at all | 68.0% |
| Baseline: earliest announcer wins ("first-spy") | 37.8% |
| Baseline: random guess among announcers | 4.5% |
| Wallet cluster purity vs. hidden truth | **99.9%** |
| Observable transactions evaluated | 332 |
| Peel-chain hops: precision / recall | 100.0% / 100.0% (published CHAIN leads that are real chains: 100.0%) |
| Merge suggestions (top 50): same operator | 13.2% (random pairs: 1.24%) |
| Lead ranker PR-AUC, with watchlist seeds / without | **1.000** / **1.000** |
| Baseline: taint alone, PR-AUC with seeds / without | 1.000 / 0.035 |
| Illicit actors ranked first (R-precision), with seeds / without | 100.0% / 100.0% (illicit share of actors: 3.5%) |
| Illicit actors found in the top 20, with seeds / without | 100.0% / 100.0% |
| Calibration error (ECE), with / without seeds | 0.003 / 0.003 |
| Stability: PR-AUC change when the country feature is removed | +0.0000 |
| Change output identified (per transaction) | **96.1%** |
| Change links used for clustering: precision | **98.8%** (82 links) |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 37.0% | 48.1% | 4.6% | 196 | 100.0% |
| 2 | 32.9% | 45.2% | 4.5% | 201 | 100.0% |
| 3 | 35.4% | 47.6% | 4.5% | 208 | 100.0% |
| 4 | 41.3% | 57.3% | 4.5% | 171 | 99.4% |
| 5 | 47.9% | 58.3% | 4.6% | 183 | 100.0% |
