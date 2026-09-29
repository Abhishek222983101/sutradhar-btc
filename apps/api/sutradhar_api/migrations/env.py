"""Alembic environment. Driven programmatically by `sutradhar_api.migrate` (no alembic.ini)."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from sutradhar_api.models import Base

url = context.config.get_main_option("sqlalchemy.url")
if not url:
    raise RuntimeError("sqlalchemy.url is not set")

engine = create_engine(url, poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
