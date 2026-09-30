# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `demo`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **39.8%** (± 3.0% across seeds) |
| Origin IP in top 3 candidates | **51.3%** |
| Random-guess baseline (informational) | 4.5% |
| Wallet cluster purity vs. hidden truth | **100.0%** |
| Observable transactions evaluated | 332 |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 38.9% | 50.0% | 4.6% | 208 | 100.0% |
| 2 | 34.2% | 43.8% | 4.5% | 216 | 100.0% |
| 3 | 41.5% | 50.0% | 4.5% | 229 | 100.0% |
| 4 | 42.7% | 58.7% | 4.5% | 186 | 100.0% |
| 5 | 41.7% | 54.2% | 4.6% | 189 | 100.0% |
