# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `rich`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **40.7%** (± 3.6% across seeds) |
| Origin IP in top 3 candidates | **53.0%** |
| Random-guess baseline (informational) | 4.4% |
| Wallet cluster purity vs. hidden truth | **100.0%** |
| Observable transactions evaluated | 1421 |
| CoinJoin detection precision / recall | **100.0%** / **100.0%** (30 CoinJoins) |
| Cluster purity if CoinJoins were merged (ablation) | 99.2% |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 38.4% | 52.3% | 4.4% | 779 | 100.0% |
| 2 | 38.9% | 50.6% | 4.4% | 745 | 100.0% |
| 3 | 42.3% | 54.9% | 4.3% | 787 | 100.0% |
| 4 | 36.9% | 50.0% | 4.4% | 771 | 100.0% |
| 5 | 47.0% | 57.2% | 4.4% | 806 | 100.0% |
