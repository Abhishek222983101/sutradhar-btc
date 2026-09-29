"""UTXO economy: wallets, coin selection, fees and transaction building with exact satoshi accounting.

Invariants (tested): every transaction conserves value (Σin = Σout + fee, fee ≥ 0), no UTXO is spent twice,
every output owned by a world wallet is credited to it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from sutradhar_gen.addresses import make_address
from sutradhar_schemas.enums import ScriptType

DUST_SATS = 546
_IN_VBYTES = {
    ScriptType.P2PKH: 148.0,
    ScriptType.P2SH: 91.0,  # P2SH-P2WPKH
    ScriptType.P2WPKH: 68.0,
    ScriptType.P2WSH: 105.0,
    ScriptType.P2TR: 57.5,
}
_OUT_VBYTES = {
    ScriptType.P2PKH: 34.0,
    ScriptType.P2SH: 32.0,
    ScriptType.P2WPKH: 31.0,
    ScriptType.P2WSH: 43.0,
    ScriptType.P2TR: 43.0,
}


def estimate_vsize(in_scripts: list[ScriptType], out_scripts: list[ScriptType]) -> int:
    overhead = 10.5 if any(s != ScriptType.P2PKH for s in in_scripts) else 10.0
    size = overhead + sum(_IN_VBYTES[s] for s in in_scripts) + sum(_OUT_VBYTES[s] for s in out_scripts)
    return math.ceil(size)


@dataclass(slots=True)
class Utxo:
    txid: str
    vout: int
    address: str
    sats: int
    script: ScriptType
    created_us: int


@dataclass(slots=True)
class TxOut:
    address: str
    sats: int
    script: ScriptType
    wallet_id: str | None
    is_change: bool = False


@dataclass(slots=True)
class Tx:
    txid: str
    ts_us: int
    inputs: list[Utxo]
    outputs: list[TxOut]
    fee_sats: int
    vsize: int
    kind: str
    sender_wallet: str | None = None
    sender_agent: str | None = None
    origin_node: int | None = None
    op_id: str | None = None
    tags: dict[str, Any] = field(default_factory=dict)

    @property
    def is_coinbase(self) -> bool:
        return not self.inputs


@dataclass(slots=True)
class Wallet:
    wallet_id: str
    agent_id: str
    script: ScriptType
    reuse_prob: float = 0.0
    change_last: bool = True
    utxos: dict[tuple[str, int], Utxo] = field(default_factory=dict)
    addresses: list[str] = field(default_factory=list)

    @property
    def balance(self) -> int:
        return sum(u.sats for u in self.utxos.values())


class InsufficientFundsError(Exception):
    """The wallet cannot fund the requested payments plus fee."""


class Ledger:
    """All wallets, the address→wallet index and every transaction, in creation order."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng
        self.wallets: dict[str, Wallet] = {}
        self.address_owner: dict[str, str] = {}
        self.change_addresses: set[str] = set()
        self.txs: list[Tx] = []
        self._spent: set[tuple[str, int]] = set()

    # -- wallets & addresses ------------------------------------------------------------------------
    def add_wallet(self, wallet: Wallet) -> Wallet:
        if wallet.wallet_id in self.wallets:
            raise ValueError(f"duplicate wallet {wallet.wallet_id}")
        self.wallets[wallet.wallet_id] = wallet
        return wallet

    def new_address(self, wallet: Wallet, *, allow_reuse: bool = True, change: bool = False) -> str:
        if allow_reuse and wallet.addresses and self.rng.random() < wallet.reuse_prob:
            return wallet.addresses[int(self.rng.integers(len(wallet.addresses)))]
        while True:
            address = make_address(wallet.script, self.rng)
            if address not in self.address_owner:
                break
        self.address_owner[address] = wallet.wallet_id
        wallet.addresses.append(address)
        if change:
            self.change_addresses.add(address)
        return address

    def new_txid(self) -> str:
        return self.rng.bytes(32).hex()

    # -- building transactions ----------------------------------------------------------------------
    def _commit(self, tx: Tx) -> Tx:
        total_in = sum(u.sats for u in tx.inputs)
        total_out = sum(o.sats for o in tx.outputs)
        if not tx.is_coinbase and total_in != total_out + tx.fee_sats:
            raise AssertionError("value not conserved")
        if tx.fee_sats < 0 or any(o.sats <= 0 for o in tx.outputs):
            raise AssertionError("negative fee or non-positive output")
        for utxo in tx.inputs:
            key = (utxo.txid, utxo.vout)
            if key in self._spent:
                raise AssertionError("double spend")
            self._spent.add(key)
            owner = self.wallets[self.address_owner[utxo.address]]
            owner.utxos.pop(key)
        for vout, out in enumerate(tx.outputs):
            if out.wallet_id is not None:
                self.wallets[out.wallet_id].utxos[(tx.txid, vout)] = Utxo(
                    tx.txid, vout, out.address, out.sats, out.script, tx.ts_us
                )
        self.txs.append(tx)
        return tx

    def _out(self, address: str, sats: int, *, change: bool = False) -> TxOut:
        owner = self.address_owner.get(address)
        script = self.wallets[owner].script if owner else ScriptType.P2WPKH
        return TxOut(address, sats, script, owner, change)

    def coinbase(self, to_address: str, sats: int, ts_us: int, *, kind: str = "coinbase", **tags: Any) -> Tx:
        tx = Tx(self.new_txid(), ts_us, [], [self._out(to_address, sats)], 0, 0, kind, tags=dict(tags))
        tx.vsize = estimate_vsize([], [tx.outputs[0].script])
        return self._commit(tx)

    def pay(
        self,
        wallet: Wallet,
        payments: list[tuple[str, int]],
        ts_us: int,
        feerate: float,
        *,
        kind: str,
        agent_id: str | None = None,
        origin_node: int | None = None,
        op_id: str | None = None,
        inputs: list[Utxo] | None = None,
        **tags: Any,
    ) -> Tx:
        """Pay `payments` from `wallet` (largest-first selection unless `inputs` is fixed), change back."""
        if not payments or any(sats <= DUST_SATS for _, sats in payments):
            raise ValueError("payments must be non-empty and above dust")
        out_scripts = [self._out(addr, sats).script for addr, sats in payments]
        target = sum(sats for _, sats in payments)
        candidates = sorted(wallet.utxos.values(), key=lambda u: (-u.sats, u.txid, u.vout))
        chosen: list[Utxo] = list(inputs) if inputs is not None else []
        change_script = wallet.script
        while True:
            vsize = estimate_vsize([u.script for u in chosen], [*out_scripts, change_script])
            fee = math.ceil(feerate * vsize)
            have = sum(u.sats for u in chosen)
            if have >= target + fee:
                break
            if inputs is not None or not candidates:
                raise InsufficientFundsError(f"{wallet.wallet_id} cannot pay {target} + fee {fee}")
            chosen.append(candidates.pop(0))
        outputs = [self._out(addr, sats) for addr, sats in payments]
        change = sum(u.sats for u in chosen) - target - fee
        if change > DUST_SATS:
            change_address = self.new_address(wallet, allow_reuse=False, change=True)
            change_out = self._out(change_address, change, change=True)
            outputs = [*outputs, change_out] if wallet.change_last else [change_out, *outputs]
        else:
            fee += change  # dust change goes to the miner
            vsize = estimate_vsize([u.script for u in chosen], out_scripts)
        tx = Tx(
            self.new_txid(),
            ts_us,
            chosen,
            outputs,
            fee,
            vsize,
            kind,
            sender_wallet=wallet.wallet_id,
            sender_agent=agent_id or wallet.agent_id,
            origin_node=origin_node,
            op_id=op_id,
            tags=dict(tags),
        )
        return self._commit(tx)

    def sweep(
        self,
        utxos: list[Utxo],
        to_address: str,
        ts_us: int,
        feerate: float,
        *,
        kind: str,
        agent_id: str,
        wallet_id: str,
        origin_node: int | None = None,
        op_id: str | None = None,
        **tags: Any,
    ) -> Tx | None:
        """Spend every given UTXO into one output (consolidation). Returns None if it would be dust."""
        if not utxos:
            return None
        out_script = self._out(to_address, 1).script
        vsize = estimate_vsize([u.script for u in utxos], [out_script])
        fee = math.ceil(feerate * vsize)
        value = sum(u.sats for u in utxos) - fee
        if value <= DUST_SATS:
            return None
        tx = Tx(
            self.new_txid(),
            ts_us,
            sorted(utxos, key=lambda u: (u.txid, u.vout)),
            [self._out(to_address, value)],
            fee,
            vsize,
            kind,
            sender_wallet=wallet_id,
            sender_agent=agent_id,
            origin_node=origin_node,
            op_id=op_id,
            tags=dict(tags),
        )
        return self._commit(tx)
