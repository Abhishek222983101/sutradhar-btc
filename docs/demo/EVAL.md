# Evaluation results

Computed by `uv run sutradhar evals report`, scenario `demo`, seeds [1, 2, 3, 4, 5]. Not hand-typed —
re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.

| Metric | Value |
|---|---|
| Origin IP found, first try (top-1) | **39.1%** (± 5.1% across seeds) |
| Origin IP in top 3 candidates | **51.3%** |
| Random-guess baseline (informational) | 4.5% |
| Wallet cluster purity vs. hidden truth | **100.0%** |
| Observable transactions evaluated | 332 |

## Per-seed detail

| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |
|---|---|---|---|---|---|
| 1 | 37.0% | 48.1% | 4.6% | 208 | 100.0% |
| 2 | 32.9% | 45.2% | 4.5% | 216 | 100.0% |
| 3 | 36.6% | 47.6% | 4.5% | 229 | 100.0% |
| 4 | 41.3% | 57.3% | 4.5% | 186 | 100.0% |
| 5 | 47.9% | 58.3% | 4.6% | 189 | 100.0% |
