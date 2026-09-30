"""Helpers shared by the routes that read a run's analysis store."""

from __future__ import annotations

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


@contextmanager
def run_store(request: Request, run: Run) -> Iterator[duckdb.DuckDBPyConnection]:
    """The run store read-only, with the dataset attached read-only as `ds`. Always closed."""
    root = request.app.state.settings.data_dir
    path = root / "runs" / run.id / "run.duckdb"
    dataset = root / "datasets" / run.dataset_id / "dataset.duckdb"
    if not path.exists() or not dataset.exists():
        raise Problem(404, "not_found", "this run's data is no longer available")
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
