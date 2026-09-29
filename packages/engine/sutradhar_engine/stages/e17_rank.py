"""E17 rank — P0.4 STUB. Flags peel-shaped transactions as low-grade TX leads so the pipeline runs end to end.

This is a labelled rule, not a model: `model_version = 'rules@0-stub'` and `calibrated = false`. P5 replaces
it with the calibrated lead ranker; nothing downstream may treat these scores as calibrated.
"""

from __future__ import annotations

import json

from sutradhar_engine.runner import RunContext, StageReport
from sutradhar_schemas.canonical import sha256_hex

LEAD_DDL = """
CREATE TABLE IF NOT EXISTS lead (
    lead_i             INTEGER PRIMARY KEY,
    lead_key           VARCHAR NOT NULL UNIQUE,
    type               VARCHAR NOT NULL CHECK (type IN ('ACTOR', 'CASHOUT', 'CHAIN', 'TX', 'IP')),
    subject_kind       VARCHAR NOT NULL,
    subject_ref        VARCHAR NOT NULL,
    p                  DOUBLE  NOT NULL CHECK (p >= 0 AND p <= 1),
    grade              VARCHAR NOT NULL CHECK (grade IN ('A', 'B', 'C')),
    priority           DOUBLE  NOT NULL,
    families           JSON    NOT NULL,
    reasons            JSON    NOT NULL,
    value_at_risk_sats BIGINT  NOT NULL,
    last_activity_us   BIGINT,
    title              VARCHAR NOT NULL,
    summary            VARCHAR NOT NULL,
    calibrated         BOOLEAN NOT NULL,
    method             VARCHAR NOT NULL,
    model_version      VARCHAR NOT NULL,
    run_id             VARCHAR NOT NULL
)
"""

STUB_P = 0.40
REASON = "Spends one coin into a small payment and a much larger remainder, the shape of a peel-chain hop."


def lead_key(lead_type: str, subject_kind: str, subject_ref: str) -> str:
    return sha256_hex(f"{lead_type}|{subject_kind}|{subject_ref}")[:16]


class RankStubStage:
    code = "E17"
    name = "rank (stub)"
    requires = ("d_tx",)
    produces = ("lead",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(LEAD_DDL)
        ratio = ctx.settings.stub_peel_ratio
        rows = con.execute(
            """
            SELECT t.txid, t.in_sats, t.first_seen_us, min(o.sats) AS small, max(o.sats) AS large
            FROM ds.tx t JOIN ds.txout o USING (txid)
            WHERE NOT t.is_coinbase AND t.n_in BETWEEN 1 AND 2 AND t.n_out = 2
            GROUP BY t.txid, t.in_sats, t.first_seen_us
            HAVING max(o.sats) >= ? * min(o.sats)
            ORDER BY t.txid
            """,
            [ratio],
        ).fetchall()
        reasons = json.dumps(
            [{"family": "FLOW", "feature": "peel_shape", "value": None, "contribution": 0.0, "text": REASON}]
        )
        batch = [
            (
                i,
                lead_key("TX", "tx", txid),
                "TX",
                "tx",
                txid,
                STUB_P,
                "C",
                STUB_P,
                '["FLOW"]',
                reasons,
                int(in_sats),
                int(first_seen),
                "Peel-shaped transaction",
                f"Transaction {txid[:12]}… splits {small} sats off a {large}-sat remainder.",
                False,
                "rule",
                "rules@0-stub",
                ctx.run_id,
            )
            for i, (txid, in_sats, first_seen, small, large) in enumerate(rows)
        ]
        if batch:
            con.executemany(
                "INSERT INTO lead VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?::JSON, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
        return StageReport(
            rows={"lead": len(batch)}, notes=["stub ranker (P0.4): uncalibrated rule, replaced in P5"]
        )


STAGE = RankStubStage()
