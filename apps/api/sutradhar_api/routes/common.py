"""Helpers shared by the routes that read a run's analysis store."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import duckdb
from fastapi import Request
from sqlalchemy.orm import Session

from sutradhar_api.access import can_see
from sutradhar_api.auth.service import Principal
from sutradhar_api.models import Run
from sutradhar_api.problems import Problem


def visible_run(db: Session, run_id: str, principal: Principal) -> Run:
    run = db.get(Run, run_id)
    if run is None or not can_see(run.created_by, principal):
        raise Problem(404, "not_found", "no such run")
    return run


_STORE_LOCKS: dict[str, threading.RLock] = {}
_STORE_LOCKS_GUARD = threading.Lock()


def store_lock(key: str) -> threading.RLock:
    """One lock per dataset: every code path that opens that dataset's DuckDB file takes it first."""
    with _STORE_LOCKS_GUARD:
        return _STORE_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def run_store(request: Request, run: Run) -> Iterator[duckdb.DuckDBPyConnection]:
    """The run store read-only, with the dataset attached read-only as `ds`. Always closed.

    Readers of one dataset take turns: DuckDB attaches a file per database instance, so two requests attaching the same
    dataset file at once fail with a file-handle conflict (the console asks for several panels of one lead together).
    Reads are milliseconds, so serialising them costs nothing noticeable and removes the race."""
    root = request.app.state.settings.data_dir
    path = root / "runs" / run.id / "run.duckdb"
    dataset = root / "datasets" / run.dataset_id / "dataset.duckdb"
    if not path.exists() or not dataset.exists():
        raise Problem(404, "not_found", "this run's data is no longer available")
    with store_lock(run.dataset_id):
        con = duckdb.connect(str(path), read_only=True)
        try:
            con.execute(f"ATTACH '{dataset.as_posix().replace(chr(39), chr(39) * 2)}' AS ds (READ_ONLY)")
            yield con
        finally:
            con.close()


def rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def has_table(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return bool(
        con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]).fetchone()[
            0
        ]
    )
