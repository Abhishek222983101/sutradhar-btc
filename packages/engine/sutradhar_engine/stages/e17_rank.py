"""E17 rank - turns evidence into ranked, explained leads: "this IP is likely behind this wallet cluster".

For each (origin IP, wallet cluster) pair, the evidence is how many of the cluster's spending transactions
this IP most probably originated, and how confident each origin call was. p = 1 - prod(1 - p_i * w) over those
transactions (each independent call adds support; w discounts a single weak call). Grades: A p>=0.85 with
3+ transactions, B p>=0.65, else C. Wording is hedged (I17). `calibrated` is false: p is a transparent
evidence score until the trained ranker replaces it, and the UI says so.
"""

from __future__ import annotations

import json
import math

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
MODEL_VERSION = "evidence@0.1"
WEAK_CALL = 0.9
MIN_P = 0.30

PAIRS_SQL = """
WITH tx_cluster AS (
  SELECT i.txid, min(c.cluster_id) AS cluster_id FROM ds.txin i JOIN cluster c USING (address) GROUP BY i.txid
), top_origin AS (SELECT txid, ip, p, sensors_first, sensors_heard FROM origin WHERE rnk = 1)
SELECT o.ip, t.cluster_id, count(*) AS n_tx, list(o.p ORDER BY o.txid) AS ps,
       sum(x.in_sats) AS value_sats, max(x.first_seen_us) AS last_us,
       (SELECT count(*) FROM cluster c2 WHERE c2.cluster_id = t.cluster_id) AS n_addr,
       avg(o.sensors_heard * 1.0) AS first_share
FROM top_origin o JOIN tx_cluster t USING (txid) JOIN ds.tx x USING (txid)
GROUP BY o.ip, t.cluster_id
"""


def lead_key(lead_type: str, subject_kind: str, subject_ref: str) -> str:
    return sha256_hex(f"{lead_type}|{subject_kind}|{subject_ref}")[:16]


def _grade(p: float, n: int) -> str:
    if p >= 0.85 and n >= 3:
        return "A"
    return "B" if p >= 0.65 else "C"


class RankStage:
    code = "E17"
    name = "rank leads"
    requires = ("d_tx",)
    produces = ("lead",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(LEAD_DDL)
        have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        pairs = con.execute(PAIRS_SQL).fetchall() if {"origin", "cluster"} <= have else []
        out = []
        for ip, cluster_id, n_tx, ps, value, last_us, n_addr, first_share in pairs:
            p = 1 - math.prod(1 - min(0.999, float(q)) * WEAK_CALL for q in ps)
            if p < MIN_P:
                continue
            grade = _grade(p, n_tx)
            subject = f"{ip}|{cluster_id}"
            reasons = [
                {
                    "family": "NET",
                    "feature": "origin_share",
                    "value": n_tx,
                    "contribution": round(p, 3),
                    "text": f"This IP was the most likely first sender for {n_tx} transaction(s) spent by this wallet cluster.",
                },
                {
                    "family": "FLOW",
                    "feature": "cluster_size",
                    "value": n_addr,
                    "contribution": round(min(1.0, n_addr / 20), 3),
                    "text": f"The wallet cluster groups {n_addr} address(es) spent together, so the link covers all of them.",
                },
                {
                    "family": "NET",
                    "feature": "sensors_heard",
                    "value": round(float(first_share), 2),
                    "contribution": round(min(1.0, float(first_share) / 5) * 0.5, 3),
                    "text": f"This IP was heard first, on average by {round(float(first_share), 1)} sensor(s) per transaction.",
                },
            ]
            out.append(
                (
                    lead_key("ACTOR", "ip_cluster", subject),
                    "ACTOR",
                    "ip_cluster",
                    subject,
                    round(p, 4),
                    grade,
                    round(p * (1 + math.log10(1 + int(value) / 1e8)), 4),
                    json.dumps(["NET", "FLOW"]),
                    json.dumps(reasons),
                    int(value),
                    int(last_us) if last_us is not None else None,
                    f"IP {ip} likely operates wallet cluster {cluster_id[:10]}",
                    f"Evidence suggests {ip} may be the network origin of {n_tx} transaction(s) from a {n_addr}-address wallet cluster. This is a lead for review, not proof of identity.",
                )
            )
        out.sort(key=lambda r: (-r[6], r[0]))
        if out:
            con.executemany(
                "INSERT INTO lead VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(i, *r, False, "evidence", MODEL_VERSION, ctx.run_id) for i, r in enumerate(out)],
            )
        return StageReport(rows={"lead": len(out)})


STAGE = RankStage()
