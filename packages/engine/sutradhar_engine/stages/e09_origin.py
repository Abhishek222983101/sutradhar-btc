"""E09 origin - which IP first put each transaction on the network?

For every transaction, each peer that announced it to a sensor is scored by how early it was heard
relative to the first announcement anywhere: score = exp(-delay / tau), normalised into a posterior over
candidate IPs. Repeated first sightings of one IP across a wallet's transactions are what E17 turns into leads. With a single record per transaction the reported
source is used as-is (confidence capped). This is the network half of the PS: "identify the origin IP".
"""

from __future__ import annotations

from sutradhar_engine.origin_model import FEATURE_SQL, load_model
from sutradhar_engine.runner import RunContext, StageReport

TAU_S = 0.25  # seconds; the first announcer leads its relays by roughly a relay hop
TOP_K = 5

SCORE_SQL = """
CREATE TABLE origin AS
WITH s AS (SELECT *, {score} AS z FROM origin_feat),
n AS (SELECT *, exp(z - max(z) OVER (PARTITION BY txid)) AS e FROM s),
p AS (SELECT *, e / sum(e) OVER (PARTITION BY txid) AS p,
             row_number() OVER (PARTITION BY txid ORDER BY z DESC, t, ip) AS rnk FROM n)
SELECT txid, ip, p, rnk::INTEGER AS rnk, sensors_heard::INTEGER AS sensors_heard, (rank = 1)::INTEGER AS sensors_first
FROM p WHERE rnk <= {top_k}
"""


class OriginStage:
    code = "E09"
    name = "origin inference"
    requires = ("d_tx",)
    produces = ("origin",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(FEATURE_SQL)
        model = load_model()
        score = model.logit_sql() if model else f"(-dt_s / {TAU_S})"
        con.execute(SCORE_SQL.format(score=score, top_k=TOP_K))
        ctx.put_meta("origin_model", model.version if model else "timing-formula")
        row = con.execute("SELECT count(DISTINCT txid) FROM origin").fetchone()
        return StageReport(
            rows={"origin_txs": int(row[0]) if row else 0},
            notes=[f"model {model.version}" if model else "no trained weights found: timing formula used"],
        )


STAGE = OriginStage()
