"""P1.1: coin selection was always largest-first. Add fifo and random as opt-in strategies (default unchanged,
so every existing caller's output stays byte-identical) and prove each picks the input set it claims to."""

from __future__ import annotations

import numpy as np
import pytest

from sutradhar_gen.economy import Ledger, Wallet
from sutradhar_schemas.enums import ScriptType


def _funded_wallet(ledger: Ledger, coins: list[int]) -> Wallet:
    wallet = ledger.add_wallet(Wallet("w0", "a0", ScriptType.P2WPKH))
    for i, sats in enumerate(coins):
        ledger.coinbase(ledger.new_address(wallet), sats, i * 1_000_000, kind="genesis")
    return wallet


def test_largest_first_is_the_default_and_picks_fewest_biggest_coins() -> None:
    ledger = Ledger(np.random.default_rng(1))
    wallet = _funded_wallet(ledger, [50_000, 500_000, 5_000_000])
    dest = ledger.new_address(ledger.add_wallet(Wallet("w1", "a1", ScriptType.P2WPKH)))
    tx = ledger.pay(wallet, [(dest, 300_000)], 10_000_000, 1.0, kind="test")
    assert len(tx.inputs) == 1
    assert tx.inputs[0].sats == 5_000_000


def test_fifo_spends_the_oldest_coin_first() -> None:
    ledger = Ledger(np.random.default_rng(2))
    wallet = _funded_wallet(
        ledger, [5_000_000, 500_000, 50_000]
    )  # created oldest -> newest, biggest -> smallest
    dest = ledger.new_address(ledger.add_wallet(Wallet("w1", "a1", ScriptType.P2WPKH)))
    tx = ledger.pay(wallet, [(dest, 300_000)], 10_000_000, 1.0, kind="test", strategy="fifo")
    assert tx.inputs[0].created_us == 0  # the coin funded first (i=0 in _funded_wallet)


def test_random_strategy_is_deterministic_for_the_same_seed() -> None:
    def run(seed: int) -> tuple[int, ...]:
        ledger = Ledger(np.random.default_rng(seed))
        wallet = _funded_wallet(ledger, [400_000, 400_000, 400_000, 400_000, 400_000])
        dest = ledger.new_address(ledger.add_wallet(Wallet("w1", "a1", ScriptType.P2WPKH)))
        tx = ledger.pay(wallet, [(dest, 900_000)], 10_000_000, 1.0, kind="test", strategy="random")
        return tuple(sorted(u.vout for u in tx.inputs))

    assert run(7) == run(7)


def test_unknown_strategy_is_rejected() -> None:
    ledger = Ledger(np.random.default_rng(3))
    wallet = _funded_wallet(ledger, [1_000_000])
    dest = ledger.new_address(ledger.add_wallet(Wallet("w1", "a1", ScriptType.P2WPKH)))
    with pytest.raises(ValueError, match="unknown coin selection strategy"):
        ledger.pay(wallet, [(dest, 100_000)], 10_000_000, 1.0, kind="test", strategy="knapsack")
