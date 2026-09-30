"""Academy attempts.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json = JSONB() if op.get_bind().dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "academy_attempts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("challenge_id", sa.Text(), nullable=False),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", name="fk_academy_attempts_user_id"),
            nullable=False,
        ),
        sa.Column("answers", json, nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_academy_attempts_challenge_id", "academy_attempts", ["challenge_id", "score"])


def downgrade() -> None:
    op.drop_table("academy_attempts")
