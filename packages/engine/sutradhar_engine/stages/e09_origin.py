"""E09 origin - which IP first put each transaction on the network?

For every transaction, each peer that announced it to a sensor is scored by how early it was heard
relative to the first announcement anywhere: score = exp(-delay / tau), normalised into a posterior over
candidate IPs. Repeated first sightings of one IP across a wallet's transactions are what E17 turns into leads. With a single record per transaction the reported
source is used as-is (confidence capped). This is the network half of the PS: "identify the origin IP".
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

TAU_S = 0.25  # seconds; the first announcer leads its relays by roughly a relay hop
TOP_K = 5

SQL = f"""
CREATE TABLE origin AS
WITH heard AS (
  SELECT txid, src_ip AS ip, min(ts_us) AS t, count(DISTINCT dst_ip) AS sensors_heard
  FROM ds.obs WHERE src_ip IS NOT NULL GROUP BY 1, 2
), scored AS (
  SELECT *, exp(-((t - min(t) OVER (PARTITION BY txid)) / 1e6) / {TAU_S}) AS s FROM heard
), norm AS (
  SELECT *, s / sum(s) OVER (PARTITION BY txid) AS p,
         row_number() OVER (PARTITION BY txid ORDER BY t, ip) AS rnk FROM scored
)
SELECT txid, ip, p, rnk::INTEGER AS rnk, sensors_heard::INTEGER AS sensors_heard,
       (rnk = 1)::INTEGER AS sensors_first FROM norm WHERE rnk <= {TOP_K}
"""


class OriginStage:
    code = "E09"
    name = "origin inference"
    requires = ("d_tx",)
    produces = ("origin",)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute(SQL)
        row = ctx.con.execute("SELECT count(DISTINCT txid) FROM origin").fetchone()
        return StageReport(rows={"origin_txs": int(row[0]) if row else 0})


STAGE = OriginStage()
