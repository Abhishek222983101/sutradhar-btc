# ADR 0003 — Two stores: mutable app DB, immutable per-run DuckDB

- **Status:** accepted · 2026-09-30
- **Blueprint:** D5, D24

## Decision
Workflow state (users, jobs, lead status, cases, audit) lives in Postgres/SQLite. Analytics and evidence live in one DuckDB file per dataset and per run, frozen and hashed when complete. Runs are full recomputations.

## Because
Evidence must be immutable and hashable; workflow must be mutable and relational. One file per run is itself the evidence artefact.
