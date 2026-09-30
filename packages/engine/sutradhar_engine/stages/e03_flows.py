"""E03 flows - value moving between wallet clusters.

Each transaction's outputs are attributed to its input clusters in proportion to the value each contributed.
The result is a weighted directed graph between clusters: who funds whom, and how much.
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

SQL = """
CREATE TABLE flow AS
WITH in_c AS (SELECT i.txid, c.cluster_id, sum(i.sats) AS sats FROM ds.txin i JOIN cluster c USING (address) GROUP BY 1, 2),
out_c AS (SELECT o.txid, c.cluster_id, sum(o.sats) AS sats FROM ds.txout o JOIN cluster c USING (address) GROUP BY 1, 2)
SELECT s.cluster_id AS src, d.cluster_id AS dst,
       sum(d.sats * s.sats * 1.0 / t.in_sats)::BIGINT AS sats, count(DISTINCT s.txid)::INTEGER AS n_tx
FROM in_c s JOIN out_c d USING (txid) JOIN ds.tx t USING (txid)
WHERE s.cluster_id <> d.cluster_id AND t.in_sats > 0
GROUP BY 1, 2
"""


class FlowStage:
    code = "E03"
    name = "value flows"
    requires = ("cluster",)
    produces = ("flow",)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute(SQL)
        row = ctx.con.execute("SELECT count(*), coalesce(sum(sats), 0) FROM flow").fetchone()
        return StageReport(rows={"flow": int(row[0]) if row else 0})


STAGE = FlowStage()
