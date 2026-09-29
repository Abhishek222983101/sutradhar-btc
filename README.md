# Sutradhar

Offline analysis of Bitcoin traffic that links the IP address that broadcast a transaction to the wallets
that moved the money — with the evidence and a calibrated confidence for every link.

Built for **Smart India Hackathon 2026 · problem statement SIH26146 (NTRO) — AI-Powered Monitoring &
Analysis of Bitcoin Transaction Traffic.**

| | |
|---|---|
| Blueprint (architecture, plan, decisions) | [`SUTRADHAR_PLATFORM_BLUEPRINT.md`](SUTRADHAR_PLATFORM_BLUEPRINT.md) |
| Invariants every change must keep | [`docs/INVARIANTS.md`](docs/INVARIANTS.md) |
| Build log (what is done, tested and security-checked) | [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) |
| Architecture decision records | [`docs/adr/`](docs/adr/) |

## Quick start

Requirements: Linux, Docker with Compose v2, [uv](https://docs.astral.sh/uv/), Node 22 and pnpm.

```bash
make setup     # Python + web dependencies
make check     # lint, module contracts, tests, security gate
uv run sutradhar --help
```

## Repository layout

```
apps/api          HTTP API and background worker (FastAPI)
apps/web          analyst console and judge landing (React)
packages/schemas  shared data contract
packages/engine   ingestion, enrichment, graph, models, explanations, evidence
packages/generator synthetic world: UTXO economy, P2P propagation, sensors, ground truth
packages/evals    ground truth, metrics, training, reports
packages/cli      the `sutradhar` command
deploy/           Docker images, compose files, air-gap bundle, Caddy
docs/             invariants, ADRs, build log, technical write-up
```

Synthetic data only. No real traffic data is ever committed to this repository.
