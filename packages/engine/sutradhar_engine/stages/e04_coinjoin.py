"""E04 CoinJoin detection - which transactions look like collaborative equal-output mixes?

A trained logistic model scores every candidate transaction (several inputs, several outputs) from its structure:
how many outputs share one value, how many distinct input addresses fund it, script homogeneity, and so on.
Transactions scoring at least `coinjoin_min_p` are flagged. E05 refuses to merge the inputs of a flagged transaction
into one wallet (invariant I8): it would join strangers.

If no trained weights are bundled the stage falls back to the scored heuristic the model replaced (equal-output count,
input count and equal-output share), so the pipeline never runs without a CoinJoin guard.
"""

from __future__ import annotations

from sutradhar_engine.coinjoin_model import FEATURE_SQL, FEATURES, MIN_INPUTS, MIN_OUTPUTS, RULE_SQL
from sutradhar_engine.linear_model import load
from sutradhar_engine.runner import RunContext, StageReport


class CoinJoinStage:
    code = "E04"
    name = "CoinJoin detection"
    requires = ("d_tx",)
    produces = ("coinjoin",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        model = load("coinjoin_lr", FEATURES)
        notes: list[str]
        if model is None:
            con.execute(RULE_SQL)
            notes = ["no trained CoinJoin model: scored heuristic used"]
        else:
            con.execute(FEATURE_SQL.format(min_in=MIN_INPUTS, min_out=MIN_OUTPUTS))
            con.execute(
                f"""CREATE TABLE coinjoin AS
                    SELECT txid, n_in, n_out, round(equal_share * n_out)::INTEGER AS n_equal,
                           1 / (1 + exp(-z)) AS p
                    FROM (SELECT *, {model.logit_sql()} AS z FROM coinjoin_feat)"""  # noqa: S608  # nosec B608 - float literals only
            )
            notes = [f"model {model.version}"]
        row = con.execute(
            "SELECT count(*) FROM coinjoin WHERE p >= ?", [ctx.settings.coinjoin_min_p]
        ).fetchone()
        return StageReport(rows={"coinjoin_flagged": int(row[0]) if row else 0}, notes=notes)


STAGE = CoinJoinStage()
