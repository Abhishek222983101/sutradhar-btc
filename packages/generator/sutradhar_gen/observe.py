"""What the network layer records, under each of the four observation models (P1.6):

VANTAGE  a few dedicated sensors log the first k announcements they each hear from their peers.
FLOW     ISP-level records: a random slice of ordinary P2P links, not a handful of fixed vantage points,
         happens to transit an instrumented network — coverage spreads thin across many destinations.
MIXED    both at once (generate.py runs both observers over the same propagation).
SINGLE   exactly one record per transaction — the origin's own first relay hop, taken as reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from sutradhar_gen.config import ObservationCfg
from sutradhar_gen.network import Topology
from sutradhar_gen.propagate import EdgeSet, Propagation


class Observer(Protocol):
    def observe(self, tx_index: int, broadcast_us: int, prop: Propagation, log: ObservationLog) -> None: ...


@dataclass(slots=True)
class ObservationLog:
    tx_index: list[int] = field(default_factory=list)
    ts_us: list[int] = field(default_factory=list)
    src_ip: list[str] = field(default_factory=list)
    src_port: list[int] = field(default_factory=list)
    dst_ip: list[str] = field(default_factory=list)
    dst_port: list[int] = field(default_factory=list)
    sensor: list[int] = field(default_factory=list)
    peer: list[int] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.ts_us)


class VantageObserver:
    """Precomputes, for every sensor, the (peer, edge index, ports) of each incoming announcement path."""

    def __init__(self, topo: Topology, edges: EdgeSet, cfg: ObservationCfg) -> None:
        self.topo = topo
        self.cfg = cfg
        edge_index = {(int(s), int(d)): i for i, (s, d) in enumerate(zip(edges.src, edges.dst, strict=True))}
        self.inbound: dict[int, list[tuple[int, int, str, int, str, int]]] = {}
        for sensor in topo.sensors:
            paths = []
            for conn in topo.conns:
                if sensor.nid not in (conn.a, conn.b):
                    continue
                if conn.a == sensor.nid:  # the sensor initiated: peer is a listener speaking from 8333
                    peer = conn.b
                    src_port, dst_port = conn.b_port, conn.a_port
                else:  # the peer initiated: it speaks from its ephemeral port to the sensor's 8333
                    peer = conn.a
                    src_port, dst_port = conn.a_port, conn.b_port
                edge = edge_index.get((peer, sensor.nid))
                if edge is None:  # peer is itself a sensor (sensors never relay)
                    continue
                paths.append((peer, edge, topo.nodes[peer].ip, src_port, sensor.ip, dst_port))
            self.inbound[sensor.nid] = sorted(paths)

    def observe(self, tx_index: int, broadcast_us: int, prop: Propagation, log: ObservationLog) -> None:
        k = self.cfg.log_first_k
        for sensor_id, paths in self.inbound.items():
            if not paths:
                continue
            peers = np.fromiter((p[0] for p in paths), dtype=np.int64, count=len(paths))
            edges = np.fromiter((p[1] for p in paths), dtype=np.int64, count=len(paths))
            heard = prop.arrival_s[peers] + prop.inv_delay_s[edges] + prop.latency_s[edges]
            finite = np.isfinite(heard)
            if not finite.any():
                continue
            order = np.argsort(np.where(finite, heard, np.inf), kind="stable")[:k]
            for j in order:
                if not finite[j]:
                    break
                peer, _, src_ip, src_port, dst_ip, dst_port = paths[int(j)]
                log.tx_index.append(tx_index)
                log.ts_us.append(broadcast_us + round(float(heard[j]) * 1_000_000))
                log.src_ip.append(src_ip)
                log.src_port.append(src_port)
                log.dst_ip.append(dst_ip)
                log.dst_port.append(dst_port)
                log.sensor.append(sensor_id)
                log.peer.append(peer)


def _edge_endpoints(topo: Topology, edges: EdgeSet) -> list[tuple[str, int, str, int]]:
    """Per edge index: (src_ip, src_port, dst_ip, dst_port), read off the connection it rides on."""
    out = []
    for i in range(len(edges.src)):
        conn = topo.conns[int(edges.conn[i])]
        u, v = int(edges.src[i]), int(edges.dst[i])
        if u == conn.a:
            src_port, dst_port = conn.a_port, conn.b_port
        else:
            src_port, dst_port = conn.b_port, conn.a_port
        out.append((topo.nodes[u].ip, src_port, topo.nodes[v].ip, dst_port))
    return out


class FlowObserver:
    """ISP-level flow records (P1.6): sampled the way real NetFlow/sFlow collectors are — a device that logged
    every packet on a backbone link would drown in volume, so it keeps a random slice of flows instead.

    The slice is a fresh random subset of *destination nodes* per transaction, not a fixed set of links: a
    backbone listener in this topology has many inbound edges (one per client that peers with it), so sampling
    per-edge would still make that listener's address show up on almost every transaction — indistinguishable
    from a dedicated sensor. Sampling per (transaction, destination) instead keeps any one address's share of
    *rows* low regardless of its in-degree, matching what
    `sutradhar_engine.ingest.xray.detect_observation_model` calls FLOW rather than VANTAGE.
    """

    def __init__(self, topo: Topology, edges: EdgeSet, cfg: ObservationCfg, rng: np.random.Generator) -> None:
        self.edges_src = edges.src
        self.conn_side = _edge_endpoints(topo, edges)
        self.coverage = cfg.flow_edge_coverage
        self.rng = rng
        by_dst: dict[int, list[int]] = {}
        for i, dst in enumerate(edges.dst):
            by_dst.setdefault(int(dst), []).append(i)
        # Sensors are the dedicated vantage points (VantageObserver's job); flow collectors sit elsewhere.
        sensor_ids = {n.nid for n in topo.sensors}
        self.by_dst = by_dst
        self.candidate_nodes = np.array([nid for nid in by_dst if nid not in sensor_ids], dtype=np.int64)

    def observe(self, tx_index: int, broadcast_us: int, prop: Propagation, log: ObservationLog) -> None:
        if len(self.candidate_nodes) == 0:
            return
        sampled = self.candidate_nodes[self.rng.random(len(self.candidate_nodes)) < self.coverage]
        for node in sampled:
            best_edge, best_when = -1, np.inf
            for i in self.by_dst[int(node)]:
                src = int(self.edges_src[i])
                arrival = prop.arrival_s[src]
                if not np.isfinite(arrival):
                    continue
                when = arrival + prop.inv_delay_s[i] + prop.latency_s[i]
                if when < best_when:
                    best_edge, best_when = i, when
            if best_edge < 0:
                continue
            src_ip, src_port, dst_ip, dst_port = self.conn_side[best_edge]
            log.tx_index.append(tx_index)
            log.ts_us.append(broadcast_us + round(float(best_when) * 1_000_000))
            log.src_ip.append(src_ip)
            log.src_port.append(src_port)
            log.dst_ip.append(dst_ip)
            log.dst_port.append(dst_port)
            log.sensor.append(-1)  # no dedicated sensor id: an ordinary link, not a vantage point
            log.peer.append(int(self.edges_src[best_edge]))


class SingleObserver:
    """Exactly one record per transaction (P1.6's `ObservationModel.SINGLE`): the origin's own first relay
    hop, nothing after it. This is the shape of a feed that reports "we saw tx X first from IP Y" with no
    propagation graph behind it — the engine takes the reported origin at face value rather than inferring it
    (see `detect_observation_model`'s `obs_per_tx_p90 <= 1` check)."""

    def __init__(self, topo: Topology, edges: EdgeSet) -> None:
        self.edges_src = edges.src
        self.conn_side = _edge_endpoints(topo, edges)
        self.by_origin: dict[int, list[int]] = {}
        for i, src in enumerate(edges.src):
            self.by_origin.setdefault(int(src), []).append(i)

    def observe(self, tx_index: int, broadcast_us: int, prop: Propagation, log: ObservationLog) -> None:
        origin = int(np.flatnonzero(prop.arrival_s == 0.0)[0]) if (prop.arrival_s == 0.0).any() else None
        if origin is None:
            return
        candidates = self.by_origin.get(origin, [])
        if not candidates:
            return
        heard = [prop.inv_delay_s[i] + prop.latency_s[i] for i in candidates]
        best = candidates[int(np.argmin(heard))]
        src_ip, src_port, dst_ip, dst_port = self.conn_side[best]
        log.tx_index.append(tx_index)
        log.ts_us.append(broadcast_us + round(float(min(heard)) * 1_000_000))
        log.src_ip.append(src_ip)
        log.src_port.append(src_port)
        log.dst_ip.append(dst_ip)
        log.dst_port.append(dst_port)
        log.sensor.append(-1)
        log.peer.append(origin)


def origin_observable(topo: Topology, origin: int) -> bool:
    """True if the origin node has a direct connection to at least one sensor."""
    sensors = {n.nid for n in topo.sensors}
    return any((c.a == origin and c.b in sensors) or (c.b == origin and c.a in sensors) for c in topo.conns)
