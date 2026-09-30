# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `demo`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **39.1%** (± 5.1% across seeds) |
| Origin IP in top 3 candidates | **51.3%** |
| Ceiling: true origin announced to a sensor at all | 68.0% |
| Baseline: earliest announcer wins ("first-spy") | 37.8% |
| Baseline: random guess among announcers | 4.5% |
| Wallet cluster purity vs. hidden truth | **99.9%** |
| Observable transactions evaluated | 332 |
| Peel-chain hops: precision / recall | 100.0% / 100.0% |
| Merge suggestions (top 50): same operator | 11.6% (random pairs: 1.23%) |
| Change output identified (per transaction) | **96.3%** |
| Change links used for clustering: precision | **99.1%** (113 links) |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 37.0% | 48.1% | 4.6% | 191 | 100.0% |
| 2 | 32.9% | 45.2% | 4.5% | 200 | 100.0% |
| 3 | 36.6% | 47.6% | 4.5% | 205 | 100.0% |
| 4 | 41.3% | 57.3% | 4.5% | 167 | 99.4% |
| 5 | 47.9% | 58.3% | 4.6% | 180 | 100.0% |
