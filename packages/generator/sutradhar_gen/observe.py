"""What the sensors record: for each transaction, the first k announcements each sensor hears from its peers.

Logging only the first few announcers per transaction is what a practical capture keeps (the earliest
relayers carry the origin signal) and it keeps datasets proportional to (transactions x sensors x k).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from sutradhar_gen.config import ObservationCfg
from sutradhar_gen.network import Topology
from sutradhar_gen.propagate import EdgeSet, Propagation


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


def origin_observable(topo: Topology, origin: int) -> bool:
    """True if the origin node has a direct connection to at least one sensor."""
    sensors = {n.nid for n in topo.sensors}
    return any((c.a == origin and c.b in sensors) or (c.b == origin and c.a in sensors) for c in topo.conns)
