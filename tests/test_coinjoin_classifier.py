"""R-PS-07: CoinJoin detection is a TRAINED classifier (coinjoin-lr@1), not just a rule.

Held-out worlds (seeds 600-601, never used for training or tuning) carry the benign look-alikes — mining pools,
payroll, merchants, traders, gambling — as hard negatives. The scored heuristic the model replaced is the baseline.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import duckdb
import polars as pl
import pytest

from sutradhar_engine import linear_model
from sutradhar_engine.coinjoin_model import FEATURE_SQL, FEATURES, MIN_INPUTS, MIN_OUTPUTS
from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.stages.e04_coinjoin import STAGE
from sutradhar_evals.metrics import build_world, coinjoin_detection
from sutradhar_evals.train_coinjoin import scenario_for
from sutradhar_gen.generate import generate

STRESS_SEEDS = (600, 601)


@pytest.fixture(scope="module")
def worlds(tmp_path_factory: pytest.TempPathFactory):
    return [build_world(scenario_for(s), s, tmp_path_factory.mktemp(f"cj{s}")) for s in STRESS_SEEDS]


@pytest.fixture(scope="module")
def ingested(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("cjds")
    generate(scenario_for(602), 602, out / "world")
    ingest([out / "world" / "data" / "traffic.csv"], CANONICAL_CSV, out / "ds", "ds_cj_602")
    return out


def _ctx(ds_dir: Path) -> SimpleNamespace:
    con = duckdb.connect()
    con.execute(f"ATTACH '{(ds_dir / 'ds' / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    return SimpleNamespace(con=con, settings=SimpleNamespace(coinjoin_min_p=0.5))


def test_trained_weights_are_bundled_and_registered() -> None:
    model = linear_model.load("coinjoin_lr", FEATURES)
    assert model is not None and model.version == "coinjoin-lr@1"
    card = json.loads((linear_model.MODELS_DIR / "coinjoin_lr.json").read_text(encoding="utf-8"))[
        "trained_on"
    ]
    assert card["validation_f1"] >= 0.95
    assert card["validation_f1"] >= card["baseline_rule_f1"] - 0.01
    assert set(card["seeds"]).isdisjoint(card["validation_seeds"])


def test_classifier_on_held_out_worlds_with_lookalike_hard_negatives(worlds) -> None:
    for world in worlds:
        cj = coinjoin_detection(world)
        assert cj.truth_coinjoins >= 3
        assert cj.precision >= 0.95 and cj.recall >= 0.95
        assert cj.precision >= cj.baseline_precision - 0.02 and cj.recall >= cj.baseline_recall - 0.02


def test_hard_negatives_are_actually_present(worlds) -> None:
    kinds = set(pl.read_parquet(worlds[0].world_dir / "truth" / "txs.parquet")["kind"].to_list())
    assert {"pool_payout", "merchant_payout", "payroll"} <= kinds


def test_coinjoin_inputs_are_never_merged_i8(worlds) -> None:
    for world in worlds:
        truth = pl.read_parquet(world.world_dir / "truth" / "txs.parquet").filter(
            (pl.col("kind") == "coinjoin") & pl.col("exported")
        )
        con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
        con.execute(f"ATTACH '{(world.dataset_dir / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
        for txid in truth["txid"].to_list():
            clusters = con.execute(
                "SELECT count(DISTINCT c.cluster_id) FROM ds.txin i JOIN cluster c USING (address) WHERE i.txid = ?",
                [txid],
            ).fetchone()[0]
            assert clusters > 1
        con.close()


def test_scoring_is_deterministic(ingested) -> None:
    def digest() -> list[tuple]:
        ctx = _ctx(ingested)
        STAGE.run(ctx)
        rows = ctx.con.execute("SELECT txid, p FROM coinjoin ORDER BY txid").fetchall()
        ctx.con.close()
        return rows

    assert digest() == digest()


def test_features_cover_only_structural_candidates(ingested) -> None:
    ctx = _ctx(ingested)
    ctx.con.execute(FEATURE_SQL.format(min_in=MIN_INPUTS, min_out=MIN_OUTPUTS))
    low = ctx.con.execute("SELECT count(*) FROM coinjoin_feat WHERE n_in < 2 OR n_out < 3").fetchone()[0]
    assert low == 0
    nulls = ctx.con.execute(
        "SELECT count(*) FROM coinjoin_feat WHERE "  # noqa: S608 - FEATURES is a fixed tuple of column names
        + " OR ".join(f"{f} IS NULL" for f in FEATURES)
    ).fetchone()[0]
    assert nulls == 0
    ctx.con.close()


def test_missing_weights_fall_back_to_the_scored_heuristic(ingested, monkeypatch, tmp_path) -> None:
    ctx = _ctx(ingested)
    trained = STAGE.run(ctx)
    flagged_trained = {r[0] for r in ctx.con.execute("SELECT txid FROM coinjoin WHERE p >= 0.5").fetchall()}
    ctx.con.close()
    assert any("coinjoin-lr@1" in n for n in trained.notes)

    empty = tmp_path / "no_models"
    empty.mkdir()
    monkeypatch.setattr(linear_model, "MODELS_DIR", empty)
    ctx = _ctx(ingested)
    fallback = STAGE.run(ctx)
    flagged_rule = {r[0] for r in ctx.con.execute("SELECT txid FROM coinjoin WHERE p >= 0.5").fetchall()}
    ctx.con.close()
    assert any("heuristic" in n for n in fallback.notes)
    assert flagged_rule and flagged_trained
    assert len(flagged_trained ^ flagged_rule) <= max(1, len(flagged_rule) // 10)
    shutil.rmtree(empty, ignore_errors=True)
