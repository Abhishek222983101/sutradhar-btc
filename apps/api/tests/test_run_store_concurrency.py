"""Several panels of one page ask for the same run at once; opening its store must not race.

DuckDB attaches a dataset file per database instance, so two requests attaching the same file at the same moment
fail with a 'file handle conflict'. The console issues four reads per lead, which exposed it as an intermittent 500."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import duckdb

from sutradhar_api.routes.common import run_store


def _fixture(tmp_path: Path):  # type: ignore[no-untyped-def]
    (tmp_path / "runs" / "run_x").mkdir(parents=True)
    (tmp_path / "datasets" / "ds_x").mkdir(parents=True)
    con = duckdb.connect(str(tmp_path / "runs" / "run_x" / "run.duckdb"))
    con.execute("CREATE TABLE cluster AS SELECT range AS n FROM range(2000)")
    con.close()
    con = duckdb.connect(str(tmp_path / "datasets" / "ds_x" / "dataset.duckdb"))
    con.execute("CREATE TABLE tx AS SELECT range AS n FROM range(2000)")
    con.close()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path)))
    )
    return request, SimpleNamespace(id="run_x", dataset_id="ds_x")


def test_many_simultaneous_readers_of_one_run_all_succeed(tmp_path: Path) -> None:
    request, run = _fixture(tmp_path)

    def read(_: int) -> int:
        with run_store(request, run) as con:  # type: ignore[arg-type]
            return int(
                con.execute(
                    "SELECT (SELECT count(*) FROM cluster) + (SELECT count(*) FROM ds.tx)"
                ).fetchone()[0]
            )

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(read, range(160)))
    assert results == [4000] * 160
