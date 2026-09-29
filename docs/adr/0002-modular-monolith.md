# ADR 0002 — Modular monolith API plus one worker process

- **Status:** accepted · 2026-09-30
- **Blueprint:** D2, D4, D6

## Decision
FastAPI modular monolith and a worker running jobs from a database-backed queue (Postgres SKIP LOCKED; embedded worker on SQLite in demo). No microservices, no serverless backend, no Redis.

## Because
Six people, ten weeks, a stateful graph engine and an air-gapped install that must stay small and boring.
