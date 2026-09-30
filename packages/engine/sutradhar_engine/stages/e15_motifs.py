"""E15 motifs - recurring transaction shapes that say something about behaviour.

consolidation: many inputs into one or two outputs (sweeping a wallet). fan_out: a few inputs paid out to many
outputs (batch payment, exchange withdrawal, market payout). coinjoin comes from E04. New motifs can be added by
a plugin stage (see `sutradhar_engine.plugins`).
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

SQL = """
CREATE TABLE motif AS
SELECT txid, CASE WHEN n_in >= 5 AND n_out <= 2 THEN 'consolidation'
                  WHEN n_in <= 3 AND n_out >= 6 THEN 'fan_out' END AS kind
FROM ds.tx WHERE NOT is_coinbase AND txid NOT IN (SELECT txid FROM coinjoin WHERE p >= 0.5)
  AND ((n_in >= 5 AND n_out <= 2) OR (n_in <= 3 AND n_out >= 6))
"""


class MotifStage:
    code = "E15"
    name = "motifs"
    requires = ("coinjoin",)
    produces = ("motif",)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute(SQL)
        rows = dict(ctx.con.execute("SELECT kind, count(*) FROM motif GROUP BY 1").fetchall())
        return StageReport(rows={f"motif_{k}": int(v) for k, v in rows.items()} or {"motif": 0})


STAGE = MotifStage()
