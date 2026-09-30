"""The shipped demo world still matches the code: unpacking works and re-running the analysis reproduces its digest."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from sutradhar_api.demo_seed import HERO_ARCHIVE
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_engine.settings import EngineSettings


def test_archive_contains_only_the_expected_files() -> None:
    with tarfile.open(HERO_ARCHIVE) as tar:
        names = sorted(m.name for m in tar.getmembers() if m.isfile())
    assert names == [
        "datasets/ds_hero/dataset.duckdb",
        "datasets/ds_hero/manifest.json",
        "datasets/ds_hero/watchlist.csv",
        "datasets/ds_hero/xray.json",
        "runs/run_hero/manifest.json",
        "runs/run_hero/run.duckdb",
    ]


@pytest.mark.slow
def test_run_is_deterministic_on_the_hero_world(tmp_path: Path) -> None:
    """Regenerate with `uv run python scripts/build_hero.py` if this fails after an intentional engine change."""
    with tarfile.open(HERO_ARCHIVE) as tar:
        tar.extractall(tmp_path, filter="data")
    shipped = json.loads((tmp_path / "runs/run_hero/manifest.json").read_text())
    again = run_pipeline(
        tmp_path / "datasets/ds_hero", tmp_path / "again", "run_hero", settings=EngineSettings(threads=2)
    )
    assert again.result_digest == shipped["result_digest"]
