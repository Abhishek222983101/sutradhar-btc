"""I5 — the audit log is append-only (database triggers) and hash-chained (tampering is detected)."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from sutradhar_api import audit
from sutradhar_api.db import Database


def _append(db: Database, n: int, actor: str = "usr_test") -> None:
    for i in range(n):
        with db.write() as session:
            audit.append(
                session,
                actor_id=actor,
                actor_role="analyst",
                action="test.event",
                target_kind="thing",
                target_ref=f"t{i}",
                payload={"i": i, "note": "ünïcode ✓", "nested": {"b": [1, 2], "a": None}},
            )
            session.commit()


def test_audit_chain_verifies(database: Database) -> None:
    _append(database, 25)
    with database.read() as session:
        result = audit.verify(session)
    assert result.ok, result
    assert result.entries == 25


def test_empty_chain_verifies(database: Database) -> None:
    with database.read() as session:
        result = audit.verify(session)
    assert result.ok
    assert (result.entries, result.head) == (0, audit.GENESIS)


@pytest.mark.security
@pytest.mark.parametrize("statement", ["UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log"])
def test_audit_append_only_trigger(database: Database, statement: str) -> None:
    _append(database, 2)
    with database.write() as session, pytest.raises(DBAPIError, match="append-only"):
        session.execute(text(statement))
        session.commit()


@pytest.mark.security
def test_audit_truncate_blocked_on_postgres(database: Database) -> None:
    if database.dialect != "postgresql":
        pytest.skip("TRUNCATE exists only on PostgreSQL")
    _append(database, 1)
    with database.write() as session, pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("TRUNCATE audit_log"))
        session.commit()


def _bypass_triggers(database: Database) -> None:
    """What an attacker with raw database access could do; the chain must still expose it."""
    with database.write() as session:
        if database.dialect == "postgresql":
            session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER USER"))
        else:
            session.execute(text("DROP TRIGGER audit_no_update"))
            session.execute(text("DROP TRIGGER audit_no_delete"))
        session.commit()


@pytest.mark.security
def test_audit_tamper_detected(database: Database) -> None:
    _append(database, 10)
    _bypass_triggers(database)
    with database.write() as session:
        session.execute(text("UPDATE audit_log SET target_ref = 'forged' WHERE seq = 4"))
        session.commit()
    with database.read() as session:
        result = audit.verify(session)
    assert not result.ok
    assert result.broken_at == 4


@pytest.mark.security
def test_audit_truncation_detected(database: Database) -> None:
    _append(database, 5)
    _bypass_triggers(database)
    with database.write() as session:
        session.execute(text("DELETE FROM audit_log WHERE seq = 5"))
        session.commit()
    with database.read() as session:
        result = audit.verify(session)
    assert not result.ok
    assert "head" in (result.reason or "")


def test_concurrent_appends_stay_gapless(database: Database) -> None:
    threads = [threading.Thread(target=_append, args=(database, 10, f"usr_{i}")) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with database.read() as session:
        result = audit.verify(session)
        seqs = [r[0] for r in session.execute(text("SELECT seq FROM audit_log ORDER BY seq"))]
    assert result.ok, result
    assert seqs == list(range(1, 61))
