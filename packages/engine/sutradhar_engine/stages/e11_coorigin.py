"""E11 co-origin - wallet clusters whose transactions keep being first-heard from the same IP.

One IP behind several clusters is the network fingerprint of one operator running several wallets. The table
holds cluster pairs with how many transactions each contributed via shared IPs.
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

SQL = """
CREATE TABLE co_origin AS
WITH tx_cluster AS (
  SELECT i.txid, min(c.cluster_id) AS cluster_id FROM ds.txin i JOIN cluster c USING (address) GROUP BY i.txid
), per AS (
  SELECT o.ip, t.cluster_id, count(*) AS n FROM origin o JOIN tx_cluster t USING (txid) WHERE o.rnk = 1 AND o.p >= 0.3 GROUP BY 1, 2
)
SELECT a.cluster_id AS a, b.cluster_id AS b, count(DISTINCT a.ip)::INTEGER AS shared_ips,
       sum(least(a.n, b.n))::INTEGER AS shared_tx
FROM per a JOIN per b ON a.ip = b.ip AND a.cluster_id < b.cluster_id
GROUP BY 1, 2
"""


class CoOriginStage:
    code = "E11"
    name = "co-origin linking"
    requires = ("origin", "cluster")
    produces = ("co_origin",)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute(SQL)
        row = ctx.con.execute("SELECT count(*) FROM co_origin").fetchone()
        return StageReport(rows={"co_origin": int(row[0]) if row else 0})


STAGE = CoOriginStage()
