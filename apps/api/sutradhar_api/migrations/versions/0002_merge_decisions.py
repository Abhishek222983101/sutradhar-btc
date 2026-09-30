"""Analyst decisions on merge suggestions (accept or reject), one per wallet-cluster pair.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merge_decisions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("a_ref", sa.Text(), nullable=False),
        sa.Column("b_ref", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "run_id", sa.Text(), sa.ForeignKey("runs.id", name="fk_merge_decisions_run_id"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("users.id", name="fk_merge_decisions_user_id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("a_ref", "b_ref", name="uq_merge_decisions_a_ref"),
        sa.CheckConstraint("decision IN ('accept', 'reject')", name="ck_merge_decisions_decision"),
    )


def downgrade() -> None:
    op.drop_table("merge_decisions")
