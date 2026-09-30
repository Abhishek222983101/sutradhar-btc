"""Flows, motifs, change model, embeddings, suggestions and the plugin hook, run end to end on a generated world."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from sutradhar_engine import plugins
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_engine.runner import RunContext, StageReport
from sutradhar_evals.metrics import build_world
from sutradhar_gen.config import PRESETS


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):
    return build_world(PRESETS["rich"], 4, tmp_path_factory.mktemp("extras"))


def _q(world, sql: str):
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_every_stage_ran(world) -> None:
    manifest = (world.run_dir / "manifest.json").read_text()
    for code in (
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
        "E07",
        "E08",
        "E09",
        "E11",
        "E12",
        "E13",
        "E14",
        "E15",
        "E16",
        "E17",
    ):
        assert f'"{code}"' in manifest


def test_flows_are_between_different_clusters_and_positive(world) -> None:
    rows = _q(world, "SELECT count(*), min(sats), sum(CASE WHEN src = dst THEN 1 ELSE 0 END) FROM flow")
    assert rows[0][0] > 0 and rows[0][1] > 0 and rows[0][2] == 0


def test_change_model_scores_outputs(world) -> None:
    assert _q(world, "SELECT count(*) FROM change")[0][0] > 0
    assert _q(world, "SELECT count(*) FROM change WHERE p < 0 OR p > 1")[0][0] == 0


def test_embeddings_have_sixteen_dimensions(world) -> None:
    dims = _q(world, "SELECT DISTINCT len(vec) FROM embedding")
    assert dims in ([(16,)], [])


def test_motifs_only_flag_non_coinjoins(world) -> None:
    assert _q(world, "SELECT count(*) FROM motif m JOIN coinjoin c USING (txid) WHERE c.p >= 0.5")[0][0] == 0


def test_suggestions_are_ordered_pairs_with_reasons(world) -> None:
    rows = _q(world, "SELECT a, b, score, reasons FROM merge_suggestion")
    assert all(a != b and 0 <= score <= 1 and reasons.startswith("[") for a, b, score, reasons in rows)


class _Plugin:
    code = "XTEST"
    name = "test plugin"
    requires = ("cluster",)
    produces = ("plugin_out",)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute("CREATE TABLE plugin_out AS SELECT count(*) AS n FROM cluster")
        return StageReport(rows={"plugin_out": 1})


def test_plugin_stage_runs_and_bad_plugins_are_skipped(
    monkeypatch: pytest.MonkeyPatch, world, tmp_path: Path
) -> None:
    good = SimpleNamespace(name="good", load=lambda: _Plugin)
    bad_code = SimpleNamespace(
        name="bad",
        load=lambda: SimpleNamespace(code="E99", name="x", requires=(), produces=(), run=lambda c: None),
    )
    broken = SimpleNamespace(name="broken", load=lambda: (_ for _ in ()).throw(ImportError("nope")))
    monkeypatch.setattr(plugins, "entry_points", lambda group: [good, bad_code, broken])
    stages = plugins.load_plugin_stages()
    assert [s.code for s in stages] == ["XTEST"]
    run_pipeline(world.dataset_dir, tmp_path / "run", "run_plugin")
    con = duckdb.connect(str(tmp_path / "run" / "run.duckdb"), read_only=True)
    assert con.execute("SELECT n FROM plugin_out").fetchone()[0] > 0
    con.close()
