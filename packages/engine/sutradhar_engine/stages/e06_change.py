"""E06 change - probability that each output of a small payment is the sender's change.

A logistic model over address freshness, script match, value rank and shape. Without trained weights the stage
writes an empty table (clustering then merges nothing extra). The model is trained in `sutradhar_evals`.
"""

from __future__ import annotations

from sutradhar_engine.change_model import FEATURE_SQL, FEATURES
from sutradhar_engine.linear_model import load
from sutradhar_engine.runner import RunContext, StageReport


class ChangeStage:
    code = "E06"
    name = "change address model"
    requires = ("coinjoin",)
    produces = ("change",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        model = load("change_lr", FEATURES)
        con.execute(
            "CREATE TABLE change (txid VARCHAR, idx INTEGER, p DOUBLE NOT NULL, PRIMARY KEY (txid, idx))"
        )
        if model is None:
            return StageReport(rows={"change": 0}, notes=["no trained change model: nothing scored"])
        con.execute(FEATURE_SQL)
        # Inputs with a NULL feature (e.g. zero-value input) are skipped rather than guessed.
        con.execute(
            f"""INSERT INTO change SELECT txid, idx, 1 / (1 + exp(-z)) AS p FROM (
                    SELECT txid, idx, {model.logit_sql()} AS z FROM change_feat
                    WHERE frac_of_input IS NOT NULL) """  # noqa: S608  # nosec B608 - the SQL holds only float literals rendered with repr()
        )
        row = con.execute("SELECT count(*), count(*) FILTER (WHERE p >= 0.9) FROM change").fetchone()
        return StageReport(
            rows={"change": int(row[0]), "confident": int(row[1])}, notes=[f"model {model.version}"]
        )


STAGE = ChangeStage()
