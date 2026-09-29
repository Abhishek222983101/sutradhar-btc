"""P0 schema: identity, sessions, datasets, runs, jobs, leads, settings and the append-only audit chain.

Revision ID: 0001
Revises:
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

GENESIS = "0" * 64


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    pg = dialect == "postgresql"
    json = JSONB() if pg else sa.JSON()
    ts = sa.DateTime(timezone=True)
    big_id = sa.BigInteger() if pg else sa.Integer()
    array_len = "jsonb_array_length" if pg else "json_array_length"

    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", ts, nullable=False),
        sa.Column("last_login_at", ts),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            _in("role", ("analyst", "lead", "admin", "auditor", "demo")), name="ck_users_role"
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("users.id", name="fk_sessions_user_id"), nullable=False
        ),
        sa.Column("created_at", ts, nullable=False),
        sa.Column("expires_at", ts, nullable=False),
        sa.Column("revoked_at", ts),
        sa.Column("revoked_reason", sa.Text()),
        sa.Column("client_ip", sa.Text()),
        sa.Column("user_agent", sa.Text()),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.ForeignKey("sessions.id", name="fk_refresh_tokens_session_id"),
            nullable=False,
        ),
        sa.Column("secret_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", ts, nullable=False),
        sa.Column("rotated_at", ts),
        sa.CheckConstraint(_in("status", ("active", "rotated", "revoked")), name="ck_refresh_tokens_status"),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_table(
        "mapping_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("spec", json, nullable=False),
        sa.Column("spec_sha256", sa.Text(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Text(), sa.ForeignKey("users.id", name="fk_mapping_profiles_created_by")),
        sa.Column("created_at", ts, nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_mapping_profiles_name"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("series_id", sa.Text()),
        sa.Column(
            "profile_id", sa.Text(), sa.ForeignKey("mapping_profiles.id", name="fk_datasets_profile_id")
        ),
        sa.Column("raw_digest", sa.Text()),
        sa.Column("normalised_digest", sa.Text()),
        sa.Column("xray", json),
        sa.Column("row_count", sa.BigInteger()),
        sa.Column("reject_count", sa.BigInteger()),
        sa.Column("bytes", sa.BigInteger()),
        sa.Column("error", sa.Text()),
        sa.Column("expires_at", ts),
        sa.Column("created_by", sa.Text(), sa.ForeignKey("users.id", name="fk_datasets_created_by")),
        sa.Column("created_at", ts, nullable=False),
        sa.CheckConstraint(
            _in("status", ("uploaded", "mapped", "validated", "normalised", "failed")),
            name="ck_datasets_status",
        ),
        sa.CheckConstraint(_in("source", ("upload", "watch", "generator", "cli")), name="ck_datasets_source"),
    )
    op.create_table(
        "dataset_files",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Text(),
            sa.ForeignKey("datasets.id", name="fk_dataset_files_dataset_id"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", ts, nullable=False),
    )
    op.create_index("ix_dataset_files_dataset_id", "dataset_files", ["dataset_id"])
    op.create_table(
        "runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "dataset_id", sa.Text(), sa.ForeignKey("datasets.id", name="fk_runs_dataset_id"), nullable=False
        ),
        sa.Column("prev_run_id", sa.Text(), sa.ForeignKey("runs.id", name="fk_runs_prev_run_id")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text()),
        sa.Column("config", json, nullable=False),
        sa.Column("model_versions", json, nullable=False),
        sa.Column("refdata_versions", json, nullable=False),
        sa.Column("manifest", json),
        sa.Column("result_digest", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", ts),
        sa.Column("finished_at", ts),
        sa.Column("created_by", sa.Text(), sa.ForeignKey("users.id", name="fk_runs_created_by")),
        sa.Column("created_at", ts, nullable=False),
        sa.CheckConstraint(
            _in("status", ("queued", "running", "completed", "failed", "published")), name="ck_runs_status"
        ),
    )
    op.create_index("ix_runs_dataset_id", "runs", ["dataset_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", json, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("locked_by", sa.Text()),
        sa.Column("locked_at", ts),
        sa.Column("heartbeat_at", ts),
        sa.Column("result", json),
        sa.Column("error", sa.Text()),
        sa.Column("created_by", sa.Text(), sa.ForeignKey("users.id", name="fk_jobs_created_by")),
        sa.Column("created_at", ts, nullable=False),
        sa.Column("started_at", ts),
        sa.Column("finished_at", ts),
        sa.UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
        sa.CheckConstraint(
            _in(
                "kind",
                (
                    "ingest",
                    "run",
                    "generate",
                    "evaluate",
                    "redteam",
                    "planner",
                    "export",
                    "verify",
                    "retrain",
                    "purge",
                    "demo_reset",
                ),
            ),
            name="ck_jobs_kind",
        ),
        sa.CheckConstraint(
            _in("status", ("queued", "running", "succeeded", "failed", "cancelled")), name="ck_jobs_status"
        ),
    )
    op.create_index(
        "ix_jobs_ready",
        "jobs",
        ["priority", "created_at"],
        sqlite_where=sa.text("status = 'queued'"),
        postgresql_where=sa.text("status = 'queued'"),
    )
    id_args: list[sa.SchemaItem] = [sa.Identity(always=True)] if pg else []
    op.create_table(
        "job_events",
        sa.Column("id", big_id, *id_args, primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Text(), sa.ForeignKey("jobs.id", name="fk_job_events_job_id"), nullable=False),
        sa.Column("ts", ts, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("data", json, nullable=False),
        sqlite_autoincrement=True,  # event ids are SSE resume points: never reused
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id", "id"])
    op.create_table(
        "leads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("runs.id", name="fk_leads_run_id"), nullable=False),
        sa.Column("lead_key", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("subject_kind", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("p", sa.Float(), nullable=False),
        sa.Column("grade", sa.Text(), nullable=False),
        sa.Column("priority", sa.Float(), nullable=False),
        sa.Column("families", json, nullable=False),
        sa.Column("reasons", json, nullable=False),
        sa.Column("value_at_risk_sats", sa.BigInteger(), nullable=False),
        sa.Column("last_activity_at", ts),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("calibrated", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("created_at", ts, nullable=False),
        sa.UniqueConstraint("run_id", "lead_key", name="uq_leads_run_id"),
        sa.CheckConstraint(_in("type", ("ACTOR", "CASHOUT", "CHAIN", "TX", "IP")), name="ck_leads_type"),
        sa.CheckConstraint(_in("grade", ("A", "B", "C")), name="ck_leads_grade"),
        sa.CheckConstraint("p >= 0 AND p <= 1", name="ck_leads_p_range"),
        sa.CheckConstraint(f"{array_len}(families) >= 1", name="ck_leads_families"),  # I6
        sa.CheckConstraint(f"{array_len}(reasons) >= 1", name="ck_leads_reasons"),  # I6
    )
    op.create_index("ix_leads_queue", "leads", ["run_id", "priority", "id"])
    op.create_table(
        "lead_state",
        sa.Column("lead_key", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("assignee_id", sa.Text(), sa.ForeignKey("users.id", name="fk_lead_state_assignee_id")),
        sa.Column("snooze_until", ts),
        sa.Column(
            "last_seen_run_id", sa.Text(), sa.ForeignKey("runs.id", name="fk_lead_state_last_seen_run_id")
        ),
        sa.Column("changed_since_review", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Text(), sa.ForeignKey("users.id", name="fk_lead_state_updated_by")),
        sa.Column("updated_at", ts, nullable=False),
        sa.CheckConstraint(
            _in("status", ("NEW", "IN_REVIEW", "ESCALATED", "CONFIRMED", "DISMISSED", "SNOOZED")),
            name="ck_lead_state_status",
        ),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", json, nullable=False),
        sa.Column("updated_by", sa.Text(), sa.ForeignKey("users.id", name="fk_settings_updated_by")),
        sa.Column("updated_at", ts, nullable=False),
    )
    _audit(pg=pg, json=json, ts=ts)


def _audit(*, pg: bool, json: sa.types.TypeEngine, ts: sa.types.TypeEngine) -> None:
    op.create_table(
        "audit_log",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("ts", ts, nullable=False),
        sa.Column("actor_id", sa.Text()),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_ref", sa.Text(), nullable=False),
        sa.Column("payload", json, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("entry_hash", name="uq_audit_log_entry_hash"),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action", "actor_id", "ts"])
    op.create_table(
        "audit_head",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_audit_head_singleton"),
    )
    op.execute(
        sa.text("INSERT INTO audit_head (id, seq, entry_hash) VALUES (1, 0, :g)").bindparams(g=GENESIS)
    )
    if pg:
        op.execute(
            """
            CREATE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'audit_log is append-only'; END $$
            """
        )
        op.execute(
            "CREATE TRIGGER audit_no_update_delete BEFORE UPDATE OR DELETE ON audit_log "
            "FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()"
        )
        op.execute(
            "CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_log "
            "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only()"
        )
        op.execute(
            """
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sutradhar_app') THEN
                REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM sutradhar_app;
              END IF;
            END $$
            """
        )
    else:
        for verb in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER audit_no_{verb.lower()} BEFORE {verb} ON audit_log "
                "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END"
            )


def downgrade() -> None:
    raise NotImplementedError("the audit chain cannot be dropped by a migration (I5)")
