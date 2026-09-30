# Security pass (P8.1)

Walked against the threat model in the blueprint §13. Every check below has a test in the suite; `not tested`
items are noted honestly.

| Area | Status | Evidence |
|---|---|---|
| Offline guard (I1) | ✅ | `test_offline_guard.py`; proven with `--network none` in CI and the compose stack |
| XXE / billion-laughs (I15) | ✅ | `test_formats.py::test_xxe_payload_rejected` |
| CSV injection neutralised (I16) | ✅ | `_safe_cell` in `cases.py`, tested via i2csv export |
| SQL injection | ✅ | All dynamic SQL uses parameterised queries or constant identifiers (bandit clean); hostile search/cursor inputs tested |
| RBAC matrix | ✅ | `test_every_mutating_endpoint_declares_permission`, role-boundary tests across every route module |
| Object-level authorisation | ✅ | demo-visitor isolation tests, `can_see`/`can_see_job` checks on every read |
| Refresh token reuse | ✅ | `test_refresh_reuse_revokes_the_whole_session`, concurrent-race test |
| Account lockout | ✅ | `test_repeated_failures_lock_the_account_temporarily` |
| Export approval gate | 🟡 not tested | `approved_by` field exists on `exports`; no route enforces it yet for escalated cases |
| Headers / CSP | ✅ | `test_security_headers`; strict CSP on `/api/docs`, `default-src 'none'` elsewhere |
| Dependency scan | ✅ | `pip-audit --skip-editable`: no known vulnerabilities |
| Secret scan | ✅ | gitleaks: no leaks found |
| SAST | ✅ | bandit clean (0 issues) |
| Password hashing | ✅ | argon2id, `test_weak_password_rejected` |
| Audit tamper detection | ✅ | `test_audit_tamper_detected`, `test_audit_truncation_detected`, append-only triggers on both dialects |
| Weak/hardcoded credentials | ✅ | `JWT_SECRET` required outside dev mode; no secrets committed (checked by gitleaks + `.gitignore`) |
| Least privilege (job subprocess) | ✅ | the ingest/run child process never receives `DATABASE_URL` or `JWT_SECRET` in its environment |
| Rate limiting | ✅ | `test_general_rate_limit`, login/demo/upload-specific limits |

**Not yet done:** a dedicated penetration test against the live deployment, and load testing at production scale
(see `scripts/bench.py` for the current numbers on generated data — 1,153 transactions analysed in 15.6s single-threaded).
