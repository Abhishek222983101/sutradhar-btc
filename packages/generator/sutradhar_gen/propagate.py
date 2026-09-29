"""Transaction propagation under Bitcoin Core's diffusion relay.

Each node that holds a transaction announces it (INV) to each peer after an independent exponential
delay — shorter for outbound peers — plus link latency; the peer then fetches it (GETDATA → TX). First
arrival times are a single-source shortest-path problem over freshly sampled delays per transaction.
Sensors are silent: they receive but never relay.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from sutradhar_gen.config import NetworkCfg
from sutradhar_gen.network import Topology


@dataclass(slots=True)
class EdgeSet:
    src: np.ndarray  # int32
    dst: np.ndarray  # int32
    conn: np.ndarray  # int32 connection index
    mean_s: np.ndarray  # float64 mean INV delay for this direction
    n_nodes: int


def build_edges(topo: Topology, cfg: NetworkCfg) -> EdgeSet:
    sensor = {n.nid for n in topo.nodes if n.kind == "sensor"}
    src, dst, conn, mean = [], [], [], []
    for ci, c in enumerate(topo.conns):
        # a initiated: for a, b is an outbound peer; for b, a is an inbound peer.
        for u, v, m in ((c.a, c.b, cfg.inv_mean_outbound_s), (c.b, c.a, cfg.inv_mean_inbound_s)):
            if u in sensor:
                continue  # sensors never relay
            src.append(u)
            dst.append(v)
            conn.append(ci)
            mean.append(m)
    return EdgeSet(
        np.asarray(src, dtype=np.int32),
        np.asarray(dst, dtype=np.int32),
        np.asarray(conn, dtype=np.int32),
        np.asarray(mean, dtype=np.float64),
        len(topo.nodes),
    )


@dataclass(slots=True)
class Propagation:
    arrival_s: np.ndarray  # first time each node holds the tx (inf if never), relative to broadcast
    inv_delay_s: np.ndarray  # per-edge INV announce delay for this tx (same order as EdgeSet)
    latency_s: np.ndarray  # per-edge one-way latency for this tx


def propagate(edges: EdgeSet, origin: int, cfg: NetworkCfg, rng: np.random.Generator) -> Propagation:
    n_edges = len(edges.src)
    inv = rng.exponential(edges.mean_s)
    latency = rng.lognormal(np.log(cfg.latency_median_ms / 1000.0), cfg.latency_sigma, size=n_edges)
    fetch = inv + 3.0 * latency  # INV, GETDATA, TX
    # csr_matrix sums duplicates; connections are unique per ordered pair so there are none.
    graph = csr_matrix((fetch, (edges.src, edges.dst)), shape=(edges.n_nodes, edges.n_nodes))
    arrival = dijkstra(graph, directed=True, indices=origin)
    return Propagation(arrival, inv, latency)
