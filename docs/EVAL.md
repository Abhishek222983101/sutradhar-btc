# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `rich`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **40.7%** (± 3.6% across seeds) |
| Origin IP in top 3 candidates | **53.0%** |
| Ceiling: true origin announced to a sensor at all | 67.6% |
| Baseline: earliest announcer wins ("first-spy") | 39.0% |
| Baseline: random guess among announcers | 4.4% |
| Wallet cluster purity vs. hidden truth | **99.9%** |
| Observable transactions evaluated | 1421 |
| CoinJoin detection precision / recall | **100.0%** / **100.0%** (30 CoinJoins) |
| Cluster purity if CoinJoins were merged (ablation) | 99.2% |
| Peel-chain hops: precision / recall | 81.6% / 100.0% |
| Merge suggestions (top 50): same operator | 37.6% (random pairs: 0.76%) |
| Change output identified (per transaction) | **94.0%** |
| Change links used for clustering: precision | **99.2%** (260 links) |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 38.4% | 52.3% | 4.4% | 728 | 100.0% |
| 2 | 38.9% | 50.6% | 4.4% | 694 | 99.9% |
| 3 | 42.3% | 54.9% | 4.3% | 743 | 100.0% |
| 4 | 36.9% | 50.0% | 4.4% | 719 | 99.9% |
| 5 | 47.0% | 57.2% | 4.4% | 759 | 100.0% |
