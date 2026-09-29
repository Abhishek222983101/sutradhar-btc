"""The `sutradhar` command end to end: generate, ingest and run through the real CLI entry point."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sutradhar_cli.main import app

runner = CliRunner()


def _ok(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result.output


def test_generate_ingest_run(tmp_path: Path) -> None:
    world = tmp_path / "world"
    assert "transactions" in _ok("gen", "run", "--scenario", "tiny", "--seed", "3", "--out", str(world))
    out = _ok(
        "ingest",
        str(world / "data" / "traffic.csv"),
        "--out",
        str(tmp_path / "datasets"),
        "--dataset-id",
        "ds_cli",
    )
    assert "ds_cli:" in out
    assert "rejects 0" in out
    assert "observation model vantage" in out
    run = _ok(
        "run", str(tmp_path / "datasets" / "ds_cli"), "--out", str(tmp_path / "runs"), "--run-id", "run_cli"
    )
    assert "result digest" in run
    assert (tmp_path / "runs" / "run_cli" / "manifest.json").exists()


def test_unknown_names_are_usage_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["gen", "run", "--scenario", "nope", "--out", str(tmp_path)])
    assert result.exit_code == 2
    assert "unknown scenario" in result.output


@pytest.mark.security
@pytest.mark.parametrize(
    "bad", ["../escape", "ds_../x", "ds_a/b", "ds_", "run_x", "ds_$(id)", "ds_" + "a" * 80]
)
def test_unsafe_dataset_ids_are_refused(tmp_path: Path, bad: str) -> None:
    csv = tmp_path / "x.csv"
    csv.write_text("timestamp\n", encoding="utf-8")
    result = runner.invoke(app, ["ingest", str(csv), "--out", str(tmp_path / "d"), "--dataset-id", bad])
    assert result.exit_code == 2
    assert not (tmp_path / "escape").exists()
    assert not any((tmp_path / "d").glob("*")) if (tmp_path / "d").exists() else True
