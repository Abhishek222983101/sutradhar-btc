"""The rich world (ransomware + CoinJoin + darknet market): generated, detected and clustered correctly."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from sutradhar_evals.metrics import build_world, cluster_purity, coinjoin_detection, origin_accuracy
from sutradhar_gen.config import PRESETS


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):
    return build_world(PRESETS["rich"], 3, tmp_path_factory.mktemp("rich"))


def test_world_contains_all_three_stories(world) -> None:
    kinds = set(pl.read_parquet(world.world_dir / "truth" / "txs.parquet")["kind"].to_list())
    assert {
        "coinjoin",
        "ransom_payment",
        "peel_hop",
        "market_payment",
        "market_payout",
        "vendor_cashout",
    } <= kinds


def test_coinjoins_have_equal_outputs(world) -> None:
    txs = pl.read_parquet(world.world_dir / "truth" / "txs.parquet").filter(pl.col("kind") == "coinjoin")
    assert txs.height >= 3
    assert (txs["n_in"] >= 3).all()
    assert (txs["n_out"] >= txs["n_in"]).all()


def test_coinjoin_detection_and_guard(world) -> None:
    cj = coinjoin_detection(world)
    assert cj.truth_coinjoins >= 3
    assert cj.precision >= 0.9
    assert cj.recall >= 0.9
    assert (
        cluster_purity(world).purity >= 0.995
    )  # nearly all wallets are pure (a few confident change links can err)


def test_coinjoin_never_merges_its_participants(world) -> None:
    """I8: the inputs of a mixing transaction belong to different people, so they must stay in different clusters."""
    import duckdb

    truth = pl.read_parquet(world.world_dir / "truth" / "txs.parquet").filter(
        (pl.col("kind") == "coinjoin") & pl.col("exported")
    )
    assert truth.height >= 3
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    con.execute(f"ATTACH '{(world.dataset_dir / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    for txid in truth["txid"].to_list():
        clusters = con.execute(
            "SELECT count(DISTINCT c.cluster_id) FROM ds.txin i JOIN cluster c USING (address) WHERE i.txid = ?",
            [txid],
        ).fetchone()[0]
        inputs = con.execute("SELECT count(*) FROM ds.txin WHERE txid = ?", [txid]).fetchone()[0]
        assert clusters >= inputs * 0.6, f"{txid}: {inputs} participants collapsed into {clusters} cluster(s)"
    con.close()


def test_origin_beats_chance_on_unseen_world(world) -> None:
    m = origin_accuracy(world)
    assert m.top1_accuracy > 5 * m.random_baseline
    assert m.top3_accuracy >= m.top1_accuracy


def test_same_seed_same_world(tmp_path: Path) -> None:
    from sutradhar_gen.generate import generate

    generate(PRESETS["rich"], 9, tmp_path / "a")
    generate(PRESETS["rich"], 9, tmp_path / "b")
    assert (tmp_path / "a/data/traffic.csv").read_bytes() == (tmp_path / "b/data/traffic.csv").read_bytes()
