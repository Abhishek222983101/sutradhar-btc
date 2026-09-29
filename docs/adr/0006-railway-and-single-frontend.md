# ADR 0006 — Railway hosts the showroom API; one frontend app hosts landing, console and metrics

- **Status:** accepted · 2026-09-30
- **Blueprint:** D16 (amended), D25 (new)

## Decision
The demo API deploys to Railway via its CLI (Render stays the documented alternative). The web app on Vercel contains the judge-facing landing, the console and the metrics page — no separate site project.

## Because
Railway and Vercel CLIs are logged in, so the whole deploy is scriptable without dashboard steps. One frontend app is more compact, works identically offline behind Caddy, and gives judges one link.
