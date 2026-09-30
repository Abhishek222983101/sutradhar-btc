"""E04 CoinJoin detection - which transactions look like collaborative equal-output mixes?

Signals: several inputs, and several outputs of exactly the same value (participants receive identical
denominations so their coins cannot be told apart). The score blends the equal-output count, the input count and the
equal-output share; transactions scoring at least `coinjoin_min_p` are flagged. E05 refuses to merge the inputs of a
flagged transaction into one wallet (invariant I8): it would join strangers.
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

MIN_INPUTS = 3
MIN_EQUAL = 3

SQL = """
CREATE TABLE coinjoin AS
WITH eq AS (SELECT txid, sats, count(*) AS c FROM ds.txout GROUP BY txid, sats),
best AS (SELECT txid, max(c) AS n_equal FROM eq GROUP BY txid)
SELECT t.txid, t.n_in, t.n_out, coalesce(b.n_equal, 1) AS n_equal,
       least(1.0, 0.5 * least(1.0, coalesce(b.n_equal, 1) / 5.0) + 0.3 * least(1.0, t.n_in / 5.0)
                  + 0.2 * (coalesce(b.n_equal, 1) * 1.0 / t.n_out)) AS p
FROM ds.tx t LEFT JOIN best b USING (txid)
WHERE NOT t.is_coinbase AND t.n_in >= {min_in} AND coalesce(b.n_equal, 1) >= {min_eq}
"""


class CoinJoinStage:
    code = "E04"
    name = "CoinJoin detection"
    requires = ("d_tx",)
    produces = ("coinjoin",)

    def run(self, ctx: RunContext) -> StageReport:
        ctx.con.execute(SQL.format(min_in=MIN_INPUTS, min_eq=MIN_EQUAL))
        row = ctx.con.execute(
            "SELECT count(*) FROM coinjoin WHERE p >= ?", [ctx.settings.coinjoin_min_p]
        ).fetchone()
        return StageReport(rows={"coinjoin_flagged": int(row[0]) if row else 0})


STAGE = CoinJoinStage()
