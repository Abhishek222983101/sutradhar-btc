"""P1.6: the generator only ever produced VANTAGE data, even though the schema (and the engine's own
`detect_observation_model`) has long understood FLOW, MIXED and SINGLE. Generate each and check the produced
data actually gets classified back as the model it claims to be."""

from __future__ import annotations

from pathlib import Path

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_gen.config import PRESETS, ObservationCfg
from sutradhar_gen.generate import generate
from sutradhar_schemas.enums import ObservationModel


def _detected_model(tmp_path: Path, model: ObservationModel, seed: int) -> ObservationModel:
    cfg = PRESETS["tiny"].model_copy(update={"observation": ObservationCfg(model=model)})
    generate(cfg, seed=seed, out=tmp_path / "world")
    result = ingest(
        [tmp_path / "world" / "data" / "traffic.csv"], CANONICAL_CSV, tmp_path / "ds", f"ds_{model.value}"
    )
    return result.capability.network.observation_model


def test_vantage_is_detected_as_vantage(tmp_path: Path) -> None:
    assert _detected_model(tmp_path, ObservationModel.VANTAGE, seed=1) == ObservationModel.VANTAGE


def test_flow_spreads_across_many_destinations_and_is_detected_as_flow(tmp_path: Path) -> None:
    assert _detected_model(tmp_path, ObservationModel.FLOW, seed=2) == ObservationModel.FLOW


def test_mixed_is_detected_as_mixed(tmp_path: Path) -> None:
    assert _detected_model(tmp_path, ObservationModel.MIXED, seed=3) == ObservationModel.MIXED


def test_single_is_detected_as_single(tmp_path: Path) -> None:
    assert _detected_model(tmp_path, ObservationModel.SINGLE, seed=4) == ObservationModel.SINGLE


def test_flow_observations_are_non_empty_and_spread_over_many_ips(tmp_path: Path) -> None:
    cfg = PRESETS["tiny"].model_copy(update={"observation": ObservationCfg(model=ObservationModel.FLOW)})
    summary = generate(cfg, seed=5, out=tmp_path)
    assert summary["counts"]["observations"] > 0
    import csv

    with (tmp_path / "data" / "traffic.csv").open() as f:
        dst_ips = {row["dst_ip"] for row in csv.DictReader(f)}
    assert len(dst_ips) >= 10  # spread thin, not concentrated on a handful of sensors
