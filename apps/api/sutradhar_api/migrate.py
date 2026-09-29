"""Apply the app database migrations: `upgrade(url)` is what `sutradhar migrate` and demo boot call."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool

MIGRATIONS = Path(__file__).parent / "migrations"


def _config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade(url: str) -> None:
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(_config(url), "head")


def head_revision() -> str | None:
    return ScriptDirectory.from_config(_config("sqlite://")).get_current_head()


def current_revision(url: str) -> str | None:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
