"""Watchlists: seed wallets and IPs handed to the risk stages, managed by lead analysts.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CATEGORIES = ("ransomware", "darknet", "scam", "theft", "sanctioned", "mixer", "other")


def upgrade() -> None:
    ts = sa.DateTime(timezone=True)
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), sa.ForeignKey("users.id", name="fk_watchlists_created_by")),
        sa.Column("created_at", ts, nullable=False),
        sa.UniqueConstraint("name", name="uq_watchlists_name"),
        sa.CheckConstraint("kind IN ('address', 'ip')", name="ck_watchlists_kind"),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "watchlist_id",
            sa.Text(),
            sa.ForeignKey("watchlists.id", name="fk_watchlist_items_watchlist_id"),
            nullable=False,
        ),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("added_by", sa.Text(), sa.ForeignKey("users.id", name="fk_watchlist_items_added_by")),
        sa.Column("added_at", ts, nullable=False),
        sa.UniqueConstraint("watchlist_id", "value", name="uq_watchlist_items_watchlist_id"),
        sa.CheckConstraint(
            "category IN (" + ", ".join(repr(c) for c in CATEGORIES) + ")", name="ck_watchlist_items_category"
        ),
        sa.CheckConstraint("confidence > 0 AND confidence <= 1", name="ck_watchlist_items_confidence"),
    )
    op.create_index("ix_watchlist_items_watchlist_id_id", "watchlist_items", ["watchlist_id", "id"])


def downgrade() -> None:
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
