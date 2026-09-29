"""Database access: one URL, a write path and a read path.

SQLite (demo) takes the write lock up front (`BEGIN IMMEDIATE`) on write sessions, so read-then-write
transactions such as the audit append can never fail half way with SQLITE_BUSY; read sessions use a deferred
BEGIN and never block writers (WAL). On PostgreSQL, read sessions run READ ONLY.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every dialect (SQLite stores naive UTC text)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: pass an aware UTC datetime")
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _sqlite_engine(url: str, *, immediate: bool) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn: Any, _record: Any) -> None:
        dbapi_conn.isolation_level = None  # SQLAlchemy emits BEGIN itself (below)
        cursor = dbapi_conn.cursor()
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA busy_timeout=30000",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA trusted_schema=OFF",
        ):
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    return engine


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        if url.startswith("sqlite"):
            self.dialect = "sqlite"
            self.write_engine = _sqlite_engine(url, immediate=True)
            self.read_engine = _sqlite_engine(url, immediate=False)
        else:
            self.dialect = "postgresql"
            self.write_engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=10)
            self.read_engine = self.write_engine.execution_options(postgresql_readonly=True)
        self._write = sessionmaker(self.write_engine, expire_on_commit=False)
        self._read = sessionmaker(self.read_engine, expire_on_commit=False)

    @contextmanager
    def write(self) -> Iterator[Session]:
        """A session for mutations. The caller commits; anything uncommitted is rolled back."""
        session = self._write()
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def read(self) -> Iterator[Session]:
        session = self._read()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.write_engine.dispose()
        if self.read_engine is not self.write_engine:
            self.read_engine.dispose()
