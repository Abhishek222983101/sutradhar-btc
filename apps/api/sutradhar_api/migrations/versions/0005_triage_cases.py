"""Triage feedback, cases, notes, exports and evidence-pack verifications.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

REASONS = (
    "benign_service",
    "victim",
    "duplicate",
    "insufficient_evidence",
    "known_false_positive_pattern",
    "other",
)


def upgrade() -> None:
    json = JSONB() if op.get_bind().dialect.name == "postgresql" else sa.JSON()
    ts = sa.DateTime(timezone=True)
    fk = lambda col, name: sa.ForeignKey(col, name=name)  # noqa: E731
    op.create_table(
        "feedback",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("lead_key", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), fk("runs.id", "fk_feedback_run_id"), nullable=False),
        sa.Column("user_id", sa.Text(), fk("users.id", "fk_feedback_user_id"), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", ts, nullable=False),
        sa.CheckConstraint("verdict IN ('confirm', 'dismiss', 'escalate')", name="ck_feedback_verdict"),
        sa.CheckConstraint(
            "verdict <> 'dismiss' OR reason_code IS NOT NULL", name="ck_feedback_dismiss_reason"
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN (" + ", ".join(repr(r) for r in REASONS) + ")",
            name="ck_feedback_reason_code",
        ),
    )
    op.create_index("ix_feedback_lead_key", "feedback", ["lead_key", "created_at"])
    op.create_table(
        "cases",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), fk("users.id", "fk_cases_owner_id"), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("created_at", ts, nullable=False),
        sa.Column("closed_at", ts),
        sa.CheckConstraint("status IN ('open', 'closed', 'archived')", name="ck_cases_status"),
    )
    op.create_table(
        "case_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("case_id", sa.Text(), fk("cases.id", "fk_case_items_case_id"), nullable=False),
        sa.Column("item_kind", sa.Text(), nullable=False),
        sa.Column("ref", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), fk("runs.id", "fk_case_items_run_id"), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("added_by", sa.Text(), fk("users.id", "fk_case_items_added_by"), nullable=False),
        sa.Column("added_at", ts, nullable=False),
        sa.UniqueConstraint("case_id", "item_kind", "ref", "run_id", name="uq_case_items_case_id"),
        sa.CheckConstraint(
            "item_kind IN ('lead', 'actor', 'address', 'tx', 'ip', 'chain')", name="ck_case_items_kind"
        ),
    )
    op.create_index("ix_case_items_case_id_added_at", "case_items", ["case_id", "added_at"])
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("case_id", sa.Text(), fk("cases.id", "fk_case_notes_case_id"), nullable=False),
        sa.Column("author_id", sa.Text(), fk("users.id", "fk_case_notes_author_id"), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("created_at", ts, nullable=False),
    )
    op.create_index("ix_case_notes_case_id_created_at", "case_notes", ["case_id", "created_at"])
    op.create_table(
        "exports",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("case_id", sa.Text(), fk("cases.id", "fk_exports_case_id")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text()),
        sa.Column("sha256", sa.Text()),
        sa.Column("bytes", sa.BigInteger()),
        sa.Column("manifest", json),
        sa.Column("error", sa.Text()),
        sa.Column("created_by", sa.Text(), fk("users.id", "fk_exports_created_by"), nullable=False),
        sa.Column("approved_by", sa.Text(), fk("users.id", "fk_exports_approved_by")),
        sa.Column("created_at", ts, nullable=False),
        sa.CheckConstraint(
            "kind IN ('evidence_pack', 'misp', 'stix', 'graphml', 'i2csv', 'pdf')", name="ck_exports_kind"
        ),
        sa.CheckConstraint("status IN ('queued', 'ready', 'failed')", name="ck_exports_status"),
    )
    op.create_table(
        "verifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("file_sha256", sa.Text(), nullable=False),
        sa.Column("result", json, nullable=False),
        sa.Column("verified_by", sa.Text(), fk("users.id", "fk_verifications_verified_by"), nullable=False),
        sa.Column("created_at", ts, nullable=False),
    )


def downgrade() -> None:
    for table in ("verifications", "exports", "case_notes", "case_items", "cases", "feedback"):
        op.drop_table(table)
