"""P2P network topology: listening nodes, clients, silent sensors, and the TCP connections between them.

A connection is initiated by one side (`a`, ephemeral source port) and accepted by a listener (`b`, port
8333). That direction matters twice: Bitcoin Core announces sooner to outbound peers than to inbound ones,
and it decides which side's port a sensor sees in its logs.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from sutradhar_gen.world import Agent, World

BITCOIN_PORT = 8333
EPHEMERAL = (32768, 60999)
TESTNET_RANGES = ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")  # RFC 5737, safe for v0


@dataclass(slots=True)
class Node:
    nid: int
    kind: str  # listener | client | sensor
    ip: str
    agent_id: str | None = None


@dataclass(slots=True)
class Conn:
    a: int  # initiator (outbound side)
    b: int  # acceptor (listener)
    a_port: int
    b_port: int = BITCOIN_PORT


@dataclass(slots=True)
class Topology:
    nodes: list[Node] = field(default_factory=list)
    conns: list[Conn] = field(default_factory=list)
    geo: dict[str, tuple[str, str]] = field(
        default_factory=dict
    )  # ip -> (country, asn); realistic space only

    @property
    def sensors(self) -> list[Node]:
        return [n for n in self.nodes if n.kind == "sensor"]

    def neighbours(self) -> dict[int, list[tuple[int, int]]]:
        """node -> [(peer, conn index)]"""
        out: dict[int, list[tuple[int, int]]] = {n.nid: [] for n in self.nodes}
        for ci, conn in enumerate(self.conns):
            out[conn.a].append((conn.b, ci))
            out[conn.b].append((conn.a, ci))
        return out


def _testnet_ips(rng: np.random.Generator, count: int) -> list[str]:
    pool = [str(ip) for net in TESTNET_RANGES for ip in ipaddress.ip_network(net).hosts()]
    if count > len(pool):
        raise ValueError(
            f"testnet IP space holds {len(pool)} hosts; {count} requested (use ip_space=realistic)"
        )
    order = rng.permutation(len(pool))[:count]
    return [pool[int(i)] for i in order]


def _realistic_ips(rng: np.random.Generator, count: int) -> tuple[list[str], dict[str, tuple[str, str]]]:
    """Public-looking addresses drawn from per-country /24 blocks of the open GeoIP database."""
    data = json.loads((Path(__file__).parent / "ip_pools.json").read_text(encoding="utf-8"))
    countries = sorted(data["weights"])
    probs = np.array([data["weights"][c] for c in countries], dtype=float)
    probs /= probs.sum()
    ips: list[str] = []
    geo: dict[str, tuple[str, str]] = {}
    while len(ips) < count:
        cc = countries[int(rng.choice(len(countries), p=probs))]
        block = data["pools"][cc][int(rng.integers(len(data["pools"][cc])))]
        ip = f"{block['prefix']}.{int(rng.integers(2, 254))}"
        if ip not in geo:
            ips.append(ip)
            geo[ip] = (cc, str(block["asn"]))
    return ips, geo


def build_topology(world: World) -> Topology:
    """Assign every agent a node, add relay listeners and sensors, and wire outbound connections."""
    cfg = world.cfg.network
    rng = world.rng["network"]
    topo = Topology()
    listener_agents = [a for a in world.agents.values() if a.kind == "exchange"]
    client_agents = [a for a in world.agents.values() if a.kind not in ("exchange",)]
    n_relays = max(0, cfg.listeners - len(listener_agents))
    total = len(listener_agents) + n_relays + cfg.sensors + len(client_agents)
    if cfg.ip_space == "realistic":
        ips, topo.geo = _realistic_ips(rng, total)
    else:
        ips = _testnet_ips(rng, total)

    def add(kind: str, agent: Agent | None) -> Node:
        node = Node(len(topo.nodes), kind, ips[len(topo.nodes)], agent.agent_id if agent else None)
        topo.nodes.append(node)
        if agent is not None:
            agent.node_id = node.nid
        return node

    listeners = [add("listener", a) for a in sorted(listener_agents, key=lambda a: a.agent_id)]
    listeners += [add("listener", None) for _ in range(n_relays)]
    sensors = [add("sensor", None) for _ in range(cfg.sensors)]
    clients = [add("client", a) for a in sorted(client_agents, key=lambda a: a.agent_id)]
    listener_ids = np.array([n.nid for n in listeners])
    sensor_ids = [n.nid for n in sensors]

    seen: set[tuple[int, int]] = set()

    def connect(a: int, b: int) -> None:
        key = (min(a, b), max(a, b))
        if a == b or key in seen:
            return
        seen.add(key)
        topo.conns.append(Conn(a, b, int(rng.integers(EPHEMERAL[0], EPHEMERAL[1] + 1))))

    for node in listeners + clients:
        peers = rng.choice(listener_ids, size=min(cfg.outbound, len(listener_ids)), replace=False)
        chosen = [int(p) for p in peers]
        if node.kind == "client" and sensor_ids and rng.random() < cfg.client_sensor_prob:
            chosen[-1] = sensor_ids[int(rng.integers(len(sensor_ids)))]
        for peer in chosen:
            connect(node.nid, peer)
    for sensor in sensors:
        peers = rng.choice(
            listener_ids, size=min(cfg.sensor_listener_links, len(listener_ids)), replace=False
        )
        for peer in peers:
            connect(sensor.nid, int(peer))
    return topo
