"""The bounded evidence subgraph of a lead (at most 150 nodes): the wallet cluster, who it trades with, the IPs behind
its payments, the route from a watchlisted wallet, and other wallets sharing its IPs. Every edge names its method,
confidence and the transactions it rests on (I2). Works on a run connection with the dataset attached as `ds`."""

from __future__ import annotations

import itertools
import json
from typing import Any

MAX_NODES = 150


def build(con, cluster_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def node(nid: str, kind: str, label: str, **attrs: Any) -> None:
        if nid not in nodes and len(nodes) < MAX_NODES:
            nodes[nid] = {"id": nid, "type": kind, "label": label, "attrs": attrs}

    def edge(kind: str, a: str, b: str, method: str, conf: float, refs: dict[str, Any]) -> None:
        if a in nodes and b in nodes:
            edges.append(
                {
                    "id": f"e{len(edges)}",
                    "type": kind,
                    "source": a,
                    "target": b,
                    "method": method,
                    "confidence": round(float(conf), 3),
                    "evidence_refs": refs,
                }
            )

    services = {r[0] for r in con.execute("SELECT cluster_id FROM service").fetchall()}
    stats = con.execute("SELECT n_addr FROM cluster_stats WHERE cluster_id = ?", [cluster_id]).fetchone()
    node(
        f"cluster:{cluster_id}",
        "cluster",
        cluster_id[:10] + "…",
        focus=True,
        addresses=int(stats[0]) if stats else 0,
    )

    for src, dst, sats, n_tx in con.execute(
        "SELECT src, dst, sats, n_tx FROM flow WHERE src = ? OR dst = ? ORDER BY sats DESC, src, dst LIMIT 24",
        [cluster_id, cluster_id],
    ).fetchall():
        other = dst if src == cluster_id else src
        node(f"cluster:{other}", "service" if other in services else "cluster", other[:10] + "…")
        edge(
            "FLOW",
            f"cluster:{src}",
            f"cluster:{dst}",
            "value-flow",
            0.9,
            {"sats": int(sats), "n_tx": int(n_tx)},
        )

    for ip, n_tx, mean_p in con.execute(
        "SELECT ip, n_tx, mean_p FROM actor_ip WHERE cluster_id = ? ORDER BY n_tx DESC, ip LIMIT 6",
        [cluster_id],
    ).fetchall():
        node(f"ip:{ip}", "ip", ip)
        txids = [
            r[0]
            for r in con.execute(
                "SELECT o.txid FROM origin o JOIN (SELECT i.txid FROM ds.txin i JOIN cluster c USING (address) WHERE c.cluster_id = ? GROUP BY 1) t USING (txid) WHERE o.rnk = 1 AND o.ip = ? ORDER BY 1 LIMIT 5",
                [cluster_id, ip],
            ).fetchall()
        ]
        edge(
            "ORIGINATED",
            f"ip:{ip}",
            f"cluster:{cluster_id}",
            "origin_model",
            mean_p,
            {"txids": txids, "n_tx": int(n_tx)},
        )

    for a, b, ips, tx in con.execute(
        "SELECT a, b, shared_ips, shared_tx FROM co_origin WHERE a = ? OR b = ? ORDER BY shared_tx DESC, a, b LIMIT 10",
        [cluster_id, cluster_id],
    ).fetchall():
        other = b if a == cluster_id else a
        node(f"cluster:{other}", "cluster", other[:10] + "…")
        edge(
            "CO_ORIGIN",
            f"cluster:{cluster_id}",
            f"cluster:{other}",
            "co_origin",
            min(1.0, tx / 4),
            {"shared_ips": int(ips), "shared_tx": int(tx)},
        )

    for _rank, path_json in con.execute(
        "SELECT rank, path FROM risk_path WHERE target = ? ORDER BY rank LIMIT 3", [cluster_id]
    ).fetchall():
        path = json.loads(path_json)
        for c in path:
            node(f"cluster:{c}", "service" if c in services else "cluster", c[:10] + "…", on_risk_path=True)
        for a, b in itertools.pairwise(path):
            edge("TAINT_PATH", f"cluster:{a}", f"cluster:{b}", "haircut-path", 0.8, {"hop": True})

    return {"nodes": list(nodes.values()), "edges": edges, "truncated": len(nodes) >= MAX_NODES}
