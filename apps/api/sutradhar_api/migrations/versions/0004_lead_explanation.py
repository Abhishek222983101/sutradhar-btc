"""Leads keep their full explanation (opposing evidence, counterfactuals, priority breakdown, provenance).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json = JSONB() if op.get_bind().dialect.name == "postgresql" else sa.JSON()
    op.add_column("leads", sa.Column("explanation", json, nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    op.drop_column("leads", "explanation")
