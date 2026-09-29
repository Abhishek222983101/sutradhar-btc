# ADR 0001 — Offline-first: one codebase, two targets

- **Status:** accepted · 2026-09-30
- **Blueprint:** D1

## Decision
The product is an air-gapped Docker Compose bundle. A cloud showroom (web on Vercel, API on Railway) runs the same images on synthetic data only.

## Because
The PS requires an offline Linux solution; judges need links. Building one codebase for both keeps the showroom honest and proves portability.
