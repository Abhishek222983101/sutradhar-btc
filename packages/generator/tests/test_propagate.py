"""Propagation reaches every connected relaying node; sensors receive but never relay."""

from __future__ import annotations

import numpy as np

from sutradhar_gen.agents import setup_exchanges, setup_users
from sutradhar_gen.config import PRESETS
from sutradhar_gen.network import build_topology
from sutradhar_gen.propagate import build_edges, propagate
from sutradhar_gen.world import World


def _world() -> tuple[World, object]:
    world = World(PRESETS["tiny"], 11)
    exchanges = setup_exchanges(world)
    setup_users(world, exchanges)
    return world, build_topology(world)


def test_propagation_reaches_all_connected() -> None:
    world, topo = _world()
    edges = build_edges(topo, world.cfg.network)
    origin = next(n.nid for n in topo.nodes if n.kind == "client")
    prop = propagate(edges, origin, world.cfg.network, np.random.default_rng(0))
    for node in topo.nodes:
        assert np.isfinite(prop.arrival_s[node.nid]), f"{node.kind} {node.nid} never received the tx"
    assert prop.arrival_s[origin] == 0.0


def test_sensors_never_relay() -> None:
    world, topo = _world()
    edges = build_edges(topo, world.cfg.network)
    sensors = {n.nid for n in topo.nodes if n.kind == "sensor"}
    assert not (set(edges.src.tolist()) & sensors)


def test_outbound_announcements_are_faster_on_average() -> None:
    world, topo = _world()
    edges = build_edges(topo, world.cfg.network)
    prop = propagate(edges, 0, world.cfg.network, np.random.default_rng(1))
    fast = prop.inv_delay_s[edges.mean_s == world.cfg.network.inv_mean_outbound_s].mean()
    slow = prop.inv_delay_s[edges.mean_s == world.cfg.network.inv_mean_inbound_s].mean()
    assert fast < slow
