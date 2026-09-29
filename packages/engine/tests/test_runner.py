"""Stage contracts and run immutability, on a hand-built dataset."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import row, txid

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import DEFAULT_STAGES, run_pipeline
from sutradhar_engine.runner import RunContext, RunError, StageReport


@pytest.fixture
def dataset(write_csv, tmp_path: Path) -> Path:
    rows = [row(txid=txid(i), output_amounts="[0.031,0.3885]") for i in range(1, 6)]
    return ingest([write_csv(rows)], CANONICAL_CSV, tmp_path / "ds", "ds_t").path


def test_stage_contracts(dataset: Path, tmp_path: Path) -> None:
    manifest = run_pipeline(dataset, tmp_path / "run", "run_t")
    for stage in DEFAULT_STAGES:
        assert stage.code in manifest.stages or stage.code == "E19"
    assert manifest.result_tables == ["d_tx", "d_addr", "d_ip", "lead"]


class _Liar:
    code = "E17"
    name = "declares a table it never makes"
    requires = ("d_tx",)
    produces = ("never_made",)

    def run(self, ctx: RunContext) -> StageReport:
        return StageReport()


def test_stage_that_breaks_its_contract_fails_the_run(dataset: Path, tmp_path: Path) -> None:
    with pytest.raises(RunError, match="did not produce"):
        run_pipeline(dataset, tmp_path / "run", "run_x", stages=(DEFAULT_STAGES[0], _Liar()))


def test_completed_run_is_read_only(dataset: Path, tmp_path: Path) -> None:
    run_pipeline(dataset, tmp_path / "run", "run_t")
    assert not (tmp_path / "run" / "run.duckdb").stat().st_mode & 0o222
    with pytest.raises(FileExistsError):
        run_pipeline(dataset, tmp_path / "run", "run_t")


@pytest.mark.security
def test_sql_hostile_paths_are_escaped(write_csv, tmp_path: Path) -> None:
    weird = tmp_path / "it's; DROP TABLE tx; --"
    ds = ingest([write_csv([row()])], CANONICAL_CSV, weird / "ds", "ds_w").path
    manifest = run_pipeline(ds, weird / "run", "run_w")
    assert manifest.result_digest


def test_empty_dataset_runs_to_an_empty_result(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    ds = ingest([empty], CANONICAL_CSV, tmp_path / "ds", "ds_empty").path
    manifest = run_pipeline(ds, tmp_path / "run", "run_empty")
    assert manifest.stages["E17"].rows == {"lead": 0}


def test_run_refuses_to_overwrite(dataset: Path, tmp_path: Path) -> None:
    run_pipeline(dataset, tmp_path / "run", "run_once")
    with pytest.raises(FileExistsError):
        run_pipeline(dataset, tmp_path / "run", "run_once")
