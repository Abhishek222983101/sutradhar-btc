# Sutradhar — architectural invariants

Load this file into every coding session (human or AI). Each invariant has a named test; CI enforces them.
Source: `SUTRADHAR_PLATFORM_BLUEPRINT.md` §3.6.

| # | Invariant | Enforced by |
|---|---|---|
| I1 | API and worker make **no outbound network connection** in `demo`/`airgap` mode | `offline_guard` · internal Docker network · `test_offline_guard_blocks_public` · `test_offline_pipeline_no_network` |
| I2 | Every derived edge carries `method`, `confidence`, `evidence_refs`, `model_version`, `run_id` | run-store DDL `NOT NULL` · `test_every_edge_has_evidence_envelope` |
| I3 | A completed run is immutable; outputs addressed by `result_digest` | read-only run file · `test_completed_run_is_read_only` |
| I4 | Same dataset + config + models ⇒ same result digest | seeded RNG, fixed threads, explicit ordering · `test_run_is_deterministic` |
| I5 | Audit log is append-only and hash-chained | DB triggers + role grants · `test_audit_chain_verifies`, `test_audit_tamper_detected` |
| I6 | Every published lead has calibrated p, grade, ≥1 reason, ≥1 family | `CHECK` constraints · `test_every_lead_has_reason_grade_calibrated_p` |
| I7 | Ground truth never reaches inference | import-linter · `test_engine_cannot_import_truth` |
| I8 | CoinJoin-scored txs (p ≥ τ) never contribute a CIOH merge | `test_cioh_excludes_coinjoin` |
| I9 | Money is int64 **satoshis** — never floats | `sutradhar_schemas.units` · `test_no_float_money` |
| I10 | Time is UTC **microseconds** (int64); display converts with an explicit offset | `test_timestamps_utc_micros` |
| I11 | The web bundle has no external URL and loads no external resource | `check-no-external-urls` · `test_web_makes_no_external_requests` |
| I12 | No list endpoint is unbounded | pagination dependency · `test_no_unpaginated_list_endpoints` |
| I13 | Every state-changing API call writes an audit entry in the same transaction | `@audited` · `test_every_mutation_emits_audit` |
| I14 | A model version serves only after passing its promotion gate | `test_promotion_blocked_below_threshold` |
| I15 | XML parsed with entities/DTDs/network disabled | `defusedxml` · `test_xxe_payload_rejected` |
| I16 | CSV exports neutralise formula injection | `safe_cell()` · `test_csv_injection_neutralised` |
| I17 | Lead text is hedged; grades never shown without evidence families | template lint · `test_reason_templates_are_hedged` |
| I18 | Module boundaries hold (schemas ← engine/gen ← evals ← api ← cli) | `.importlinter` · `test_import_contract` |
| I19 | Demo uploads are deleted after their TTL | `test_demo_upload_ttl_purge` |
| I20 | Every reference dataset carries source, licence and as-of date | `refdata/manifest.json` · `test_enrichment_provenance_present` |

## Rules for every change (humans and AI agents)

1. Never add a network call to the engine, API or worker.
2. Never import `sutradhar_gen`, `sutradhar_evals` or ground-truth files from `sutradhar_engine`.
3. Money is integer satoshis; time is UTC microseconds.
4. Every inferred edge carries an evidence envelope; every mutation is audited.
5. Thresholds live in settings, never as constants in stage code.
6. A sub-phase is done only when `make check` is green (lint, tests, security).
