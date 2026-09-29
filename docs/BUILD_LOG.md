# Build log

Every sub-phase is marked done only after `make check` passes: lint, module contracts, tests and the
security gate (ruff S-rules, bandit, pip-audit, gitleaks, security tests, pnpm audit).

Legend: ✅ done · 🔨 in progress · ⏳ not started

| Sub-phase | Status | Tests | Security gate | Notes |
|---|---|---|---|---|
| P0.1 Repository, workspaces, tooling | ✅ | 10 passed | ruff-S ✓ bandit ✓ pip-audit ✓ gitleaks ✓ (1 reviewed FP) | uv workspace, 5 import contracts, CI |
| P0.2 Data contract v1 and shared schemas | ✅ | 74 passed (26 security) | ruff-S ✓ bandit ✓ pip-audit ✓ gitleaks ✓ | Security tests caught 2 real input-handling gaps (huge exponents, underscore numerals) — fixed |
| P0.3 Generator v0 ("tiny") | ⏳ | | | |
| P0.4 Engine skeleton | ⏳ | | | |
| P0.5 API skeleton | ⏳ | | | |
| P0.6 Web shell | ⏳ | | | |
| P0.7 Deploy skeleton | ⏳ | | | |
| P0.8 Offline skeleton | ⏳ | | | |
| P1.1 Economy and wallets | ⏳ | | | |
| P1.2 Benign agents | ⏳ | | | |
| P1.3 CoinJoin coordinators | ⏳ | | | |
| P1.4 Illicit operations | ⏳ | | | |
| P1.5 P2P network and propagation | ⏳ | | | |
| P1.6 Observation models | ⏳ | | | |
| P1.7 Truth, exporters and variants | ⏳ | | | |
| P1.8 Scenario packs, randomisation, realism, CLI | ⏳ | | | |
| P2.1 Streaming readers | ⏳ | | | |
| P2.2 Mapping profiles and the auto-mapper | ⏳ | | | |
| P2.3 Normalisation | ⏳ | | | |
| P2.4 Validation and rejects | ⏳ | | | |
| P2.5 Reconcile, capability profile, X-ray | ⏳ | | | |
| P2.6 Enrichment (E02) | ⏳ | | | |
| P2.7 Reference-data pipeline | ⏳ | | | |
| P2.8 Ingest API and UI | ⏳ | | | |
| P3.1 E03 flows | ⏳ | | | |
| P3.2 E04 CoinJoin + coinjoin_clf | ⏳ | | | |
| P3.3 E05 clustering with the CoinJoin guard | ⏳ | | | |
| P3.4 E06 change + change_clf | ⏳ | | | |
| P3.5 E07 peel chains + peel_scorer | ⏳ | | | |
| P3.6 E08 motifs + plugin SDK | ⏳ | | | |
| P3.7 E12 embeddings | ⏳ | | | |
| P3.8 Training pipeline v1 | ⏳ | | | |
| P3.9 Evaluation harness v1 + metrics page v0 | ⏳ | | | |
| P4.1 E09 timing | ⏳ | | | |
| P4.2 E10 features and baselines | ⏳ | | | |
| P4.3 origin_ranker | ⏳ | | | |
| P4.4 E11 control, crowdedness, co-origin | ⏳ | | | |
| P4.5 E13 entity resolution, suggestions, assertions | ⏳ | | | |
| P4.6 Behavioural fingerprints | ⏳ | | | |
| P4.7 Network evaluation and targets review | ⏳ | | | |

## Deviations from the blueprint

| Date | Change | Why | ADR |
|---|---|---|---|
| 2026-09-30 | Demo API on Railway instead of Render | Railway and Vercel CLIs are logged in; fully scriptable deploy | 0006 |
| 2026-09-30 | Landing, console and metrics in one web app (no separate Astro site) | One link for judges, identical offline, more compact | 0006 |
