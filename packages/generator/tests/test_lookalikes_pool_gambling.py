"""P1.2: mining-pool and gambling-site lookalikes — the two agent types the module docstring long promised but
`config.PRESETS` never turned on. Generate a small world with them enabled and check their transaction shapes
land in truth with the kinds the engine and detectors would see."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from sutradhar_gen.config import PRESETS, LookalikeCfg
from sutradhar_gen.generate import generate


def test_pool_and_gambling_agents_produce_expected_tx_kinds(tmp_path: Path) -> None:
    cfg = PRESETS["tiny"].model_copy(deep=True)
    cfg = cfg.model_copy(
        update={
            "lookalikes": LookalikeCfg(pools=1, pool_miners=6, gambling_sites=1, gambling_bets_per_day=40)
        }
    )
    generate(cfg, seed=7, out=tmp_path)
    txs = pl.read_parquet(tmp_path / "truth" / "txs.parquet")
    kinds = set(txs["kind"].to_list())
    assert "pool_block" in kinds
    assert "gambling_bet" in kinds

    agents = pl.read_parquet(tmp_path / "truth" / "agents.parquet")
    assert (agents["kind"] == "pool").any()
    assert (agents["kind"] == "gambling").any()


def test_pool_payout_is_a_wide_fan_out(tmp_path: Path) -> None:
    cfg = PRESETS["tiny"].model_copy(deep=True)
    cfg = cfg.model_copy(
        update={
            "lookalikes": LookalikeCfg(
                pools=1, pool_miners=8, pool_block_every_h=0.5, pool_payout_every_h=2.0
            )
        }
    )
    generate(cfg, seed=11, out=tmp_path)
    txs = pl.read_parquet(tmp_path / "truth" / "txs.parquet")
    payouts = txs.filter(pl.col("kind") == "pool_payout")
    assert payouts.height >= 1
    assert (payouts["n_out"] >= 2).all()
