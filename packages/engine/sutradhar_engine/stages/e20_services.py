"""E20 services - which wallet clusters are infrastructure (exchanges, batch payers) rather than individual actors?

Flagging a service matters twice: taint stops at a service (its funds are mixed with everyone's), and a service is
never turned into an actor lead. Two type rules, both scored 0 to 1:
  exchange     many addresses and many counterparties (deposit addresses swept together, many customers)
  batch_payer  regularly pays many outputs in one transaction (withdrawal batches, payouts)
`cluster_stats` (structure per cluster) is also the base for the actor features used by the lead ranker.
"""

from __future__ import annotations

import math

from sutradhar_engine.runner import RunContext, StageReport

STATS_SQL = """
CREATE TABLE cluster_stats AS
WITH tx_actor AS (
  SELECT i.txid, min(c.cluster_id) AS cluster_id FROM ds.txin i JOIN cluster c USING (address) GROUP BY i.txid
), sent AS (
  SELECT a.cluster_id, count(*) AS n_tx_sent, avg(t.n_in) AS avg_n_in, avg(t.n_out) AS avg_n_out,
         sum(t.in_sats) AS sent_sats, min(t.first_seen_us) AS first_us, max(t.first_seen_us) AS last_us
  FROM tx_actor a JOIN ds.tx t USING (txid) GROUP BY 1
), recv AS (
  SELECT c.cluster_id, count(DISTINCT o.txid) AS n_tx_recv, sum(o.sats) AS recv_sats
  FROM ds.txout o JOIN cluster c USING (address) GROUP BY 1
), size AS (SELECT cluster_id, count(*) AS n_addr FROM cluster GROUP BY 1),
cp AS (
  SELECT c, count(DISTINCT o) AS n_counterparties FROM (
    SELECT src AS c, dst AS o FROM flow UNION ALL SELECT dst, src FROM flow) GROUP BY 1
)
SELECT s.cluster_id, s.n_addr, coalesce(se.n_tx_sent, 0) AS n_tx_sent, coalesce(r.n_tx_recv, 0) AS n_tx_recv,
       coalesce(cp.n_counterparties, 0) AS n_counterparties, coalesce(se.avg_n_in, 0) AS avg_n_in,
       coalesce(se.avg_n_out, 0) AS avg_n_out, coalesce(se.sent_sats, 0) AS sent_sats, coalesce(r.recv_sats, 0) AS recv_sats,
       se.first_us, se.last_us
FROM size s LEFT JOIN sent se USING (cluster_id) LEFT JOIN recv r USING (cluster_id) LEFT JOIN cp ON cp.c = s.cluster_id
"""


def exchange_score(n_addr: int, counterparties: int) -> float:
    return min(
        1.0,
        0.5 * min(1.0, math.log1p(n_addr) / math.log(101))
        + 0.5 * min(1.0, math.log1p(counterparties) / math.log(201)),
    )


def batch_score(avg_n_out: float, n_tx_sent: int) -> float:
    if n_tx_sent < 3:
        return 0.0
    return min(1.0, max(0.0, (avg_n_out - 3) / 8) * min(1.0, n_tx_sent / 6))


class ServiceStage:
    code = "E20"
    name = "services"
    requires = ("flow",)
    produces = ("cluster_stats", "service")

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(STATS_SQL)
        con.execute(
            "CREATE TABLE service (cluster_id VARCHAR PRIMARY KEY, kind VARCHAR NOT NULL, score DOUBLE NOT NULL)"
        )
        rows = []
        for cid, n_addr, sent, cps, avg_out in con.execute(
            "SELECT cluster_id, n_addr, n_tx_sent, n_counterparties, avg_n_out FROM cluster_stats"
        ).fetchall():
            ex, ba = exchange_score(int(n_addr), int(cps)), batch_score(float(avg_out), int(sent))
            score, kind = (ex, "exchange") if ex >= ba else (ba, "batch_payer")
            if score >= ctx.settings.service_min_score:
                rows.append((cid, kind, round(score, 4)))
        if rows:
            con.executemany("INSERT INTO service VALUES (?, ?, ?)", sorted(rows))
        kinds = {k: sum(1 for r in rows if r[1] == k) for k in ("exchange", "batch_payer")}
        return StageReport(rows={"service": len(rows), **{f"service_{k}": v for k, v in kinds.items() if v}})


STAGE = ServiceStage()
