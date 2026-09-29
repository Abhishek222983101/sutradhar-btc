"""E08 anomaly - an Isolation Forest over transaction shape scores how statistically unusual each one is.

Features: log input value, inputs, outputs, fee rate, and the spread between the biggest and smallest output.
The forest is unsupervised and seeded (I4). Scores are rank-normalised to 0..1 so they read as "more unusual
than X% of the dataset".
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from sutradhar_engine.runner import RunContext, StageReport

FEATURES_SQL = """
SELECT t.txid, t.in_sats, t.n_in, t.n_out, t.fee_sats,
       coalesce(max(o.sats) * 1.0 / nullif(min(o.sats), 0), 1.0) AS spread
FROM ds.tx t JOIN ds.txout o USING (txid) WHERE NOT t.is_coinbase GROUP BY ALL ORDER BY t.txid
"""
MIN_ROWS = 30


class AnomalyStage:
    code = "E08"
    name = "anomaly detection"
    requires = ("d_tx",)
    produces = ("anomaly",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        rows = con.execute(FEATURES_SQL).fetchall()
        con.execute("CREATE TABLE anomaly (txid VARCHAR PRIMARY KEY, score DOUBLE NOT NULL)")
        if len(rows) < MIN_ROWS:
            return StageReport(rows={"anomaly": 0}, notes=["too few transactions for an unsupervised model"])
        x = np.array(
            [
                [np.log1p(r[1]), r[2], r[3], r[4] / max(1.0, r[2] * 68 + r[3] * 31 + 11), np.log1p(r[5])]
                for r in rows
            ],
            dtype=float,
        )
        forest = IsolationForest(n_estimators=200, random_state=ctx.settings.seed, n_jobs=1).fit(x)
        raw = -forest.score_samples(x)
        rank = raw.argsort().argsort() / max(1, len(raw) - 1)
        con.executemany(
            "INSERT INTO anomaly VALUES (?, ?)", [(r[0], float(s)) for r, s in zip(rows, rank, strict=True)]
        )
        return StageReport(rows={"anomaly": len(rows)})


STAGE = AnomalyStage()
