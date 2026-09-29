# ADR 0005 — No blockchain anchoring; local hash chain

- **Status:** accepted · 2026-09-30
- **Blueprint:** D18, D20

## Decision
Tamper evidence is a local SHA-256 hash-chained audit log plus per-pack SHA-256 hash reports (BSA 2023 s.63 aligned). No Solana or other public-chain anchoring.

## Because
Offline requirement; writing investigation metadata to a public chain would leak that an investigation exists; a one-party chain adds no trust.
