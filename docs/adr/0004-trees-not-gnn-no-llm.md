# ADR 0004 — LightGBM with native TreeSHAP; no GNN core, no LLM

- **Status:** accepted · 2026-09-30
- **Blueprint:** D7, D8, D19

## Decision
Tree ensembles (LightGBM, deterministic mode) for every supervised model, explanations via pred_contrib, randomized-SVD embeddings, deterministic templates for narratives.

## Because
Trees beat GNNs on this class of data (Weber 2019; Elliptic++ 2023), run on CPU, reproduce exactly and explain exactly. An LLM would break offline operation and add hallucination liability.
