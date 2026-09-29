"""End to end: generate → ingest → run. Deterministic result digests (I4) and frozen outputs (I3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_gen.config import PRESETS
from sutradhar_gen.generate import generate
from sutradhar_schemas.enums import ObservationModel


@pytest.fixture(scope="module")
def tiny_dataset(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("e2e")
    generate(PRESETS["tiny"], 1, root / "world")
    return ingest([root / "world" / "data" / "traffic.csv"], CANONICAL_CSV, root / "ds", "ds_tiny").path


def test_tiny_world_ingests_cleanly(tiny_dataset: Path) -> None:
    import json

    xray = json.loads((tiny_dataset / "xray.json").read_text())
    assert xray["quality"]["rejects"] == 0
    assert xray["network"]["observation_model"] == ObservationModel.VANTAGE
    assert xray["network"]["sensors_inferred"] == PRESETS["tiny"].network.sensors


def test_run_is_deterministic(tiny_dataset: Path, tmp_path: Path) -> None:
    a = run_pipeline(tiny_dataset, tmp_path / "a", "run_a")
    b = run_pipeline(tiny_dataset, tmp_path / "b", "run_b")
    assert a.result_digest == b.result_digest
    assert a.dataset["normalised_digest"] == b.dataset["normalised_digest"]
