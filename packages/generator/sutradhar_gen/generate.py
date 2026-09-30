"""Generate a world: simulate the economy, propagate every transaction, record what sensors see, export.

Output layout (blueprint §5.8):
    <out>/data/traffic.{csv,json,ndjson,xml}   what the system sees (PS minimum fields + extras); csv unless
                                                `fmt` says otherwise — same content, same row order, any format
    <out>/data/watchlist.csv    partial seeds handed to the system
    <out>/truth/*.parquet       ground truth — only sutradhar_evals may read it (I7)
    <out>/world.json            scenario, seed, generator version, counts
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sutradhar_gen import __version__
from sutradhar_gen.agents import ExchangeState, setup_exchanges, setup_users
from sutradhar_gen.config import ScenarioConfig
from sutradhar_gen.export import (
    write_canonical_csv,
    write_canonical_json,
    write_canonical_ndjson,
    write_canonical_xml,
    write_parquet,
)
from sutradhar_gen.lookalikes import setup_lookalikes
from sutradhar_gen.network import Topology, build_topology
from sutradhar_gen.observe import (
    FlowObserver,
    ObservationLog,
    Observer,
    SingleObserver,
    VantageObserver,
    origin_observable,
)
from sutradhar_gen.ops import DarknetState, RansomwareState, setup_coinjoin, setup_darknet, setup_ransomware
from sutradhar_gen.propagate import build_edges, propagate
from sutradhar_gen.world import World
from sutradhar_schemas.enums import ObservationModel

_WRITERS = {
    "csv": (write_canonical_csv, "traffic.csv"),
    "json": (write_canonical_json, "traffic.json"),
    "ndjson": (write_canonical_ndjson, "traffic.ndjson"),
    "xml": (write_canonical_xml, "traffic.xml"),
}


def generate(cfg: ScenarioConfig, seed: int, out: Path, fmt: str = "csv") -> dict[str, Any]:
    world = World(cfg, seed)
    exchanges = setup_exchanges(world)
    users = setup_users(world, exchanges)
    ops: list = [setup_ransomware(world, rc, users, exchanges) for rc in cfg.ops.ransomware]
    ops += [setup_darknet(world, dc, users, exchanges) for dc in cfg.ops.darknet]
    for cc in cfg.ops.coinjoin:
        setup_coinjoin(world, cc, users)
    lk = cfg.lookalikes
    if lk.merchants or lk.payroll_employers or lk.traders or lk.pools or lk.gambling_sites:
        setup_lookalikes(world, lk, users)
    topo = build_topology(world)
    world.run()

    exported = [
        tx
        for tx in world.ledger.txs
        if not tx.is_coinbase and tx.ts_us >= world.t_export and tx.origin_node is not None
    ]
    edges = build_edges(topo, cfg.network)
    model = cfg.observation.model
    observers: list[Observer] = []
    if model in (ObservationModel.VANTAGE, ObservationModel.MIXED):
        observers.append(VantageObserver(topo, edges, cfg.observation))
    if model in (ObservationModel.FLOW, ObservationModel.MIXED):
        observers.append(FlowObserver(topo, edges, cfg.observation, world.rng["observation"]))
    if model == ObservationModel.SINGLE:
        observers.append(SingleObserver(topo, edges))
    log = ObservationLog()
    rng = world.rng["propagation"]
    for i, tx in enumerate(exported):
        prop = propagate(edges, tx.origin_node, cfg.network, rng)  # type: ignore[arg-type]
        for observer in observers:
            observer.observe(i, tx.ts_us, prop, log)

    if fmt not in _WRITERS:
        raise ValueError(f"unknown format {fmt!r}; choose from {sorted(_WRITERS)}")
    writer, filename = _WRITERS[fmt]
    data_dir, truth_dir = out / "data", out / "truth"
    rows = writer(data_dir / filename, exported, log, topo.geo)
    _write_watchlist(data_dir / "watchlist.csv", ops)
    _write_truth(truth_dir, world, topo, exchanges, exported)

    summary = {
        "generator_version": __version__,
        "scenario": cfg.model_dump(mode="json"),
        "seed": seed,
        "window_us": [world.t_export, world.t_end],
        "counts": {
            "agents": len(world.agents),
            "txs_simulated": len(world.ledger.txs),
            "txs_exported": len(exported),
            "observations": rows,
            "nodes": len(topo.nodes),
            "sensors": len(topo.sensors),
            "connections": len(topo.conns),
        },
    }
    (out / "world.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _write_watchlist(path: Path, ops: list[RansomwareState | DarknetState]) -> None:
    """Hand the system only part of what is known: the first ransom address of each operation."""
    lines = ["address,category,source,confidence"]
    for state in ops:
        if isinstance(state, DarknetState):
            if state.escrow_first:
                lines.append(f"{state.escrow_first},darknet,market seizure,0.9")
            continue
        if state.ransom_utxos:
            first = sorted(state.ransom_utxos, key=lambda u: u.created_us)[0]
            lines.append(f"{first.address},ransomware,victim report,0.95")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_truth(
    truth_dir: Path, world: World, topo: Topology, exchanges: list[ExchangeState], exported: list
) -> None:
    ledger = world.ledger
    deposit_of = {addr: customer for ex in exchanges for customer, addr in ex.customer_deposit.items()}

    write_parquet(
        truth_dir / "agents.parquet",
        [
            {
                "agent_id": a.agent_id,
                "kind": a.kind,
                "illicit": a.illicit,
                "op_id": a.op_id,
                "node_id": a.node_id,
                "victim_of": a.attrs.get("victim_of"),
            }
            for a in world.agents.values()
        ],
        {"agent_id": str, "kind": str, "illicit": bool, "op_id": str, "node_id": int, "victim_of": str},
    )
    write_parquet(
        truth_dir / "addresses.parquet",
        [
            {
                "address": addr,
                "wallet_id": wid,
                "agent_id": ledger.wallets[wid].agent_id,
                "script_type": str(ledger.wallets[wid].script),
                "is_change": addr in ledger.change_addresses,
                "deposit_of": deposit_of.get(addr),
            }
            for addr, wid in ledger.address_owner.items()
        ],
        {
            "address": str,
            "wallet_id": str,
            "agent_id": str,
            "script_type": str,
            "is_change": bool,
            "deposit_of": str,
        },
    )
    exported_ids = {tx.txid for tx in exported}
    write_parquet(
        truth_dir / "txs.parquet",
        [
            {
                "txid": tx.txid,
                "ts_us": tx.ts_us,
                "kind": tx.kind,
                "sender_agent": tx.sender_agent,
                "op_id": tx.op_id,
                "n_in": len(tx.inputs),
                "n_out": len(tx.outputs),
                "fee_sats": tx.fee_sats,
                "vsize": tx.vsize,
                "exported": tx.txid in exported_ids,
                "peel_chain_id": tx.tags.get("peel_chain_id"),
                "peel_hop": tx.tags.get("peel_hop"),
                "victim": tx.tags.get("victim"),
            }
            for tx in ledger.txs
        ],
        {
            "txid": str,
            "ts_us": int,
            "kind": str,
            "sender_agent": str,
            "op_id": str,
            "n_in": int,
            "n_out": int,
            "fee_sats": int,
            "vsize": int,
            "exported": bool,
            "peel_chain_id": str,
            "peel_hop": int,
            "victim": str,
        },
    )
    write_parquet(
        truth_dir / "outputs.parquet",
        [
            {
                "txid": tx.txid,
                "vout": vout,
                "address": o.address,
                "sats": o.sats,
                "is_change": o.is_change,
                "owner_agent": ledger.wallets[o.wallet_id].agent_id if o.wallet_id else None,
            }
            for tx in exported
            for vout, o in enumerate(tx.outputs)
        ],
        {"txid": str, "vout": int, "address": str, "sats": int, "is_change": bool, "owner_agent": str},
    )
    write_parquet(
        truth_dir / "origins.parquet",
        [
            {
                "txid": tx.txid,
                "origin_node": tx.origin_node,
                "origin_ip": topo.nodes[tx.origin_node].ip,
                "observable": origin_observable(topo, tx.origin_node),
            }
            for tx in exported
        ],
        {"txid": str, "origin_node": int, "origin_ip": str, "observable": bool},
    )
    write_parquet(
        truth_dir / "nodes.parquet",
        [{"node_id": n.nid, "kind": n.kind, "ip": n.ip, "agent_id": n.agent_id} for n in topo.nodes],
        {"node_id": int, "kind": str, "ip": str, "agent_id": str},
    )
