"""E21 risk - who is connected to the seeds, by how much, through what, and where does the money go?

* victims: clusters that sent most of their value to tainted clusters, only a few times, and are not tainted
  themselves. They paid; they are not perpetrators, and are never turned into actor leads.
* personalized PageRank from the seed clusters over the value-flow graph: a smooth "closeness to the seeds".
* k-best paths from a seed to each top-ranked cluster (Yen's algorithm on -log of each hop's share of the sender's
  outflow), so a lead can show *how* risk reaches it.
* cash-out candidates: non-service clusters holding tainted funds that send most of their outflow to a service.
"""

from __future__ import annotations

import itertools
import json
import math

import networkx as nx
import numpy as np
import scipy.sparse as sp

from sutradhar_engine.runner import RunContext, StageReport

TAINT_CLUSTER_SQL = "SELECT c.cluster_id, max(t.taint), bool_or(t.is_seed), min(t.hops) FROM taint t JOIN cluster c USING (address) GROUP BY 1"
VICTIM_MAX_SENDS = 3
VICTIM_MIN_EXPOSURE = 0.5
VICTIM_TAINT_TARGET = 0.5


class RiskStage:
    code = "E21"
    name = "risk paths, victims and cash-outs"
    requires = ("taint", "service", "flow", "cluster_stats")
    produces = ("cluster_risk", "victim", "risk_path", "cashout")

    def run(self, ctx: RunContext) -> StageReport:
        con, s = ctx.con, ctx.settings
        risk = {r[0]: (float(r[1]), bool(r[2]), int(r[3])) for r in con.execute(TAINT_CLUSTER_SQL).fetchall()}
        services = {r[0] for r in con.execute("SELECT cluster_id FROM service").fetchall()}
        flows = con.execute("SELECT src, dst, sats FROM flow").fetchall()
        stats = {
            r[0]: r[1:] for r in con.execute("SELECT cluster_id, n_tx_sent FROM cluster_stats").fetchall()
        }
        out_total: dict[str, int] = {}
        for src, _, sats in flows:
            out_total[src] = out_total.get(src, 0) + int(sats)

        # ── victims ──
        con.execute("CREATE TABLE victim (cluster_id VARCHAR PRIMARY KEY, exposure_out DOUBLE NOT NULL)")
        exposure: dict[str, float] = {}
        for src, dst, sats in flows:
            if risk.get(dst, (0, False, 9))[0] >= VICTIM_TAINT_TARGET:
                exposure[src] = exposure.get(src, 0) + int(sats)
        victims = [
            (c, round(v / out_total[c], 4))
            for c, v in sorted(exposure.items())
            if out_total.get(c)
            and v / out_total[c] >= VICTIM_MIN_EXPOSURE
            and int(stats.get(c, (0,))[0]) <= VICTIM_MAX_SENDS
            and risk.get(c, (0, False, 9))[0] < 0.05
            and c not in services
        ]
        if victims:
            con.executemany("INSERT INTO victim VALUES (?, ?)", victims)
        victim_ids = {v[0] for v in victims}

        # ── personalized PageRank over the flow graph ──
        nodes = sorted(
            {c for src, dst, _ in flows for c in (src, dst)} | {c for c, (_, seed, _) in risk.items() if seed}
        )
        index = {c: i for i, c in enumerate(nodes)}
        con.execute(
            "CREATE TABLE cluster_risk (cluster_id VARCHAR PRIMARY KEY, taint DOUBLE NOT NULL, hops INTEGER NOT NULL, ppr DOUBLE NOT NULL, is_seed BOOLEAN NOT NULL)"
        )
        seed_nodes = [c for c, (_, is_seed, _) in risk.items() if is_seed and c in index]
        ppr = np.zeros(len(nodes))
        if nodes and seed_nodes:
            rows = [index[a] for a, b, _ in flows if a not in services]
            cols = [
                index[b] for a, b, _ in flows if a not in services
            ]  # money does not flow *through* a service
            data = [float(w) for (a, _, w) in flows if a not in services]
            m = sp.csr_matrix((data, (rows, cols)), shape=(len(nodes), len(nodes)))
            deg = np.asarray(m.sum(axis=1)).ravel()
            deg[deg == 0] = 1.0
            trans = (sp.diags(1 / deg) @ m).T.tocsr()
            restart = np.zeros(len(nodes))
            for c in seed_nodes:
                restart[index[c]] = 1.0
            restart /= restart.sum()
            ppr = restart.copy()
            for _ in range(60):
                ppr = s.ppr_alpha * (trans @ ppr) + (1 - s.ppr_alpha) * restart
        risk_rows = [
            (
                c,
                risk.get(c, (0.0, False, 9))[0],
                min(risk.get(c, (0, False, 9))[2], 9),
                float(ppr[index[c]]) if c in index else 0.0,
                risk.get(c, (0, False, 9))[1],
            )
            for c in nodes
        ]
        if risk_rows:
            con.executemany("INSERT INTO cluster_risk VALUES (?, ?, ?, ?, ?)", risk_rows)

        # ── k-best paths from the seeds to the top-ranked clusters ──
        con.execute(
            "CREATE TABLE risk_path (target VARCHAR, rank INTEGER, hops INTEGER, cost DOUBLE, path VARCHAR NOT NULL, PRIMARY KEY (target, rank))"
        )
        n_paths = 0
        if seed_nodes:
            graph = nx.DiGraph()
            for a, b, w in flows:
                if a in services and a not in seed_nodes:
                    continue
                share = int(w) / out_total[a]
                if graph.has_edge(a, b):
                    share += math.exp(-graph[a][b]["weight"])
                graph.add_edge(a, b, weight=-math.log(min(1.0, max(share, 1e-9))))
            graph.add_node("__seed__")
            for c in seed_nodes:
                graph.add_edge("__seed__", c, weight=0.0)
            ranked = sorted(
                (c for c in nodes if c not in seed_nodes and c not in services and ppr[index[c]] > 0),
                key=lambda c: (-ppr[index[c]], c),
            )
            rows = []
            for target in ranked[: s.risk_paths_top]:
                if not nx.has_path(graph, "__seed__", target):
                    continue
                for rank, path in enumerate(
                    itertools.islice(
                        nx.shortest_simple_paths(graph, "__seed__", target, weight="weight"), s.risk_paths_k
                    )
                ):
                    cost = sum(graph[a][b]["weight"] for a, b in itertools.pairwise(path))
                    rows.append((target, rank, len(path) - 2, round(cost, 4), json.dumps(path[1:])))
            if rows:
                con.executemany("INSERT INTO risk_path VALUES (?, ?, ?, ?, ?)", rows)
            n_paths = len(rows)

        # ── cash-out candidates ──
        con.execute(
            "CREATE TABLE cashout (cluster_id VARCHAR, service_id VARCHAR, sats BIGINT, share DOUBLE, taint DOUBLE, PRIMARY KEY (cluster_id, service_id))"
        )
        cash = []
        for src, dst, sats in flows:
            t = risk.get(src, (0.0, False, 9))[0]
            if (
                dst in services
                and src not in services
                and src not in victim_ids
                and t >= s.cashout_min_taint
                and out_total.get(src)
            ):
                share = int(sats) / out_total[src]
                if share >= 0.5:
                    cash.append((src, dst, int(sats), round(share, 4), round(t, 4)))
        if cash:
            con.executemany("INSERT INTO cashout VALUES (?, ?, ?, ?, ?)", sorted(cash))
        return StageReport(rows={"victim": len(victims), "risk_path": n_paths, "cashout": len(cash)})


STAGE = RiskStage()
