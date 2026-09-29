"""World generation: deterministic, PS-shaped output, conserved value, the ransomware story present."""

from __future__ import annotations

import csv
import hashlib
import ipaddress
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from sutradhar_gen.agents import setup_exchanges, setup_users
from sutradhar_gen.config import PRESETS
from sutradhar_gen.generate import generate
from sutradhar_gen.network import TESTNET_RANGES, build_topology
from sutradhar_gen.ops import setup_ransomware
from sutradhar_gen.world import World
from sutradhar_schemas import PS_MINIMUM_FIELDS, CanonicalRecord, to_sats
from sutradhar_schemas.units import utc_micros

TINY = PRESETS["tiny"]


@pytest.fixture(scope="module")
def world_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("tiny")
    generate(TINY, 1, out)
    return out


def _digest_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_generator_deterministic(world_dir: Path, tmp_path: Path) -> None:
    generate(TINY, 1, tmp_path)
    assert _digest_tree(world_dir) == _digest_tree(tmp_path)


def test_different_seeds_differ(world_dir: Path, tmp_path: Path) -> None:
    generate(TINY, 2, tmp_path)
    assert _digest_tree(world_dir)["data/traffic.csv"] != _digest_tree(tmp_path)["data/traffic.csv"]


def test_generator_exports_minimum_fields(world_dir: Path) -> None:
    with (world_dir / "data" / "traffic.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(PS_MINIMUM_FIELDS) <= set(reader.fieldnames or [])
        rows = list(reader)
    assert len(rows) > 1000
    import json

    for row in rows[:300]:
        record = CanonicalRecord(
            ts_us=utc_micros(datetime.fromisoformat(row["timestamp"])),
            txid=row["txid"],
            src_ip=row["src_ip"],
            src_port=int(row["src_port"]),
            dst_ip=row["dst_ip"],
            dst_port=int(row["dst_port"]),
            input_addresses=tuple(json.loads(row["input_addresses"])),
            input_sats=tuple(to_sats(v, "btc") for v in json.loads(row["input_amounts"], parse_float=str)),
            output_addresses=tuple(json.loads(row["output_addresses"])),
            output_sats=tuple(to_sats(v, "btc") for v in json.loads(row["output_amounts"], parse_float=str)),
            fee_sats=to_sats(row["fee"], "btc"),
        )
        assert record.computed_fee_sats == record.fee_sats


def test_data_dir_contains_no_truth(world_dir: Path) -> None:
    assert sorted(p.name for p in (world_dir / "data").iterdir()) == ["traffic.csv", "watchlist.csv"]


def test_utxo_conservation_and_no_double_spend() -> None:
    world = World(TINY, 3)
    exchanges = setup_exchanges(world)
    users = setup_users(world, exchanges)
    for rc in TINY.ops.ransomware:
        setup_ransomware(world, rc, users, exchanges)
    build_topology(world)
    world.run()
    spent: set[tuple[str, int]] = set()
    for tx in world.ledger.txs:
        if tx.is_coinbase:
            continue
        assert sum(u.sats for u in tx.inputs) == sum(o.sats for o in tx.outputs) + tx.fee_sats
        assert tx.fee_sats >= 0
        for u in tx.inputs:
            assert (u.txid, u.vout) not in spent
            spent.add((u.txid, u.vout))


def test_ransomware_story_present(world_dir: Path) -> None:
    txs = pl.read_parquet(world_dir / "truth" / "txs.parquet").filter(pl.col("op_id") == "ghostline")
    kinds = txs["kind"].value_counts().sort("kind")
    counts = dict(zip(kinds["kind"], kinds["count"], strict=True))
    assert counts["ransom_payment"] == TINY.ops.ransomware[0].victims
    assert counts["consolidation"] == 1
    assert counts["peel_hop"] == TINY.ops.ransomware[0].peel_hops
    consolidation = txs.filter(pl.col("kind") == "consolidation")
    assert consolidation["n_in"][0] == counts["ransom_payment"]
    hops = txs.filter(pl.col("kind") == "peel_hop").sort("peel_hop")
    assert hops["peel_hop"].to_list() == list(range(TINY.ops.ransomware[0].peel_hops))
    assert (hops["n_in"] == 1).all()
    assert (hops["n_out"] == 2).all()


@pytest.mark.security
def test_testnet_worlds_use_only_documentation_ips(world_dir: Path) -> None:
    """v0 worlds must never point at real hosts: every IP is in an RFC 5737 documentation range."""
    nets = [ipaddress.ip_network(n) for n in TESTNET_RANGES]
    with (world_dir / "data" / "traffic.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for ip in (row["src_ip"], row["dst_ip"]):
                assert any(ipaddress.ip_address(ip) in net for net in nets), ip
