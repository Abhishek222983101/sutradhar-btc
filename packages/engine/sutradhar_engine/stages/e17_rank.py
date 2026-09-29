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


def _row(
    kind: str,
    subject_kind: str,
    subject: str,
    p: float,
    families: list[str],
    reasons: list,
    value: int,
    last_us: int | None,
    title: str,
    summary: str,
) -> tuple:
    p = round(min(0.99, p), 4)
    return (
        lead_key(kind, subject_kind, subject),
        kind,
        subject_kind,
        subject,
        p,
        _grade(p, 0 if p < 0.85 else 3),
        round(p * (1 + math.log10(1 + value / 1e8)), 4),
        json.dumps(families),
        json.dumps(reasons),
        value,
        last_us,
        title,
        summary,
    )


def _chain_leads(con, have: set[str]) -> list[tuple]:
    if "peel_chain" not in have:
        return []
    rows = con.execute(
        "SELECT chain_id, count(*), sum(remainder_sats), max(ts_us), min(txid) FROM peel_chain GROUP BY 1 ORDER BY 1"
    ).fetchall()
    return [
        _row(
            "CHAIN",
            "chain",
            chain_id,
            0.45 + 0.08 * hops,
            ["FLOW"],
            [
                {
                    "family": "FLOW",
                    "feature": "peel_hops",
                    "value": hops,
                    "contribution": round(0.08 * hops, 3),
                    "text": f"{hops} consecutive transactions each pay out a small amount and pass the remainder on, the shape of a peeling chain.",
                }
            ],
            int(value),
            int(last),
            f"Peeling chain of {hops} hops",
            f"A {hops}-hop sequence starting at transaction {first[:10]} moves most of its value onward while peeling off small payments. This is a lead for review, not proof of wrongdoing.",
        )
        for chain_id, hops, value, last, first in rows
    ]


def _anomaly_leads(con, have: set[str]) -> list[tuple]:
    if "anomaly" not in have:
        return []
    rows = con.execute(
        "SELECT a.txid, a.score, x.in_sats, x.n_in, x.n_out, x.first_seen_us FROM anomaly a JOIN ds.tx x USING (txid) "
        "WHERE a.score >= 0.97 ORDER BY a.score DESC, a.txid LIMIT 8"
    ).fetchall()
    return [
        _row(
            "TX",
            "tx",
            txid,
            0.3 + 0.3 * (score - 0.97) / 0.03,
            ["ANOM"],
            [
                {
                    "family": "ANOM",
                    "feature": "isolation_score",
                    "value": round(score, 3),
                    "contribution": round(score, 3),
                    "text": f"An unsupervised model rates this transaction (inputs {n_in}, outputs {n_out}) as more unusual than {round(score * 100)}% of the dataset.",
                }
            ],
            int(sats),
            int(ts),
            f"Statistically unusual transaction {txid[:10]}",
            "The transaction's shape (value, fee rate, split) is atypical for this dataset. Unusual is not the same as illicit; treat as a lead for review.",
        )
        for txid, score, sats, n_in, n_out, ts in rows
    ]


def _taint_leads(con, have: set[str], taint_of: dict[str, float]) -> list[tuple]:
    if not taint_of:
        return []
    seed_clusters = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT c.cluster_id FROM cluster c JOIN taint t USING (address) WHERE t.is_seed"
        ).fetchall()
    }
    out = []
    for cluster_id, t in sorted(taint_of.items()):
        if t < 0.2:
            continue
        seed = cluster_id in seed_clusters
        n_addr, value = con.execute(
            "SELECT count(*), coalesce((SELECT sum(o.sats) FROM ds.txout o JOIN cluster c2 ON c2.address = o.address WHERE c2.cluster_id = ?), 0) FROM cluster WHERE cluster_id = ?",
            [cluster_id, cluster_id],
        ).fetchone()
        out.append(
            _row(
                "ACTOR",
                "cluster",
                cluster_id,
                0.55 + 0.4 * t if not seed else 0.9,
                ["TAINT", "FLOW"],
                [
                    {
                        "family": "TAINT",
                        "feature": "taint_share",
                        "value": round(t, 3),
                        "contribution": round(t, 3),
                        "text": (
                            "This wallet cluster contains a watchlisted seed address."
                            if seed
                            else f"About {round(t * 100)}% of this wallet cluster's value traces back to a watchlisted wallet through the ledger."
                        ),
                    }
                ],
                int(value),
                None,
                f"Wallet cluster {cluster_id[:10]} " + ("is a seed wallet" if seed else "holds traced funds"),
                f"{n_addr} address(es) spent together. Risk reaches this cluster by value-weighted propagation from watchlisted wallets. Lead for review.",
            )
        )
    return out


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
        taint_of: dict[str, float] = {}
        if {"taint", "cluster"} <= have:
            taint_of = dict(
                con.execute(
                    "SELECT c.cluster_id, max(t.taint) FROM cluster c JOIN taint t USING (address) GROUP BY 1"
                ).fetchall()
            )
        geo: dict[str, tuple] = {}
        if "ip_geo" in have:
            geo = {r[0]: r[1:] for r in con.execute("SELECT ip, country, asn, org FROM ip_geo").fetchall()}
        out = []
        for ip, cluster_id, n_tx, ps, value, last_us, n_addr, first_share in pairs:
            p = 1 - math.prod(1 - min(0.999, float(q)) * WEAK_CALL for q in ps)
            if p < MIN_P:
                continue
            tainted = taint_of.get(cluster_id, 0.0)
            families = ["NET", "FLOW"]
            extra = []
            if tainted >= 0.05:
                p = 1 - (1 - p) * (1 - 0.6 * tainted)
                families.append("TAINT")
                extra = [
                    {
                        "family": "TAINT",
                        "feature": "taint_share",
                        "value": round(tainted, 3),
                        "contribution": round(0.6 * tainted, 3),
                        "text": f"About {round(tainted * 100)}% of the value in this wallet cluster traces back to a watchlisted wallet.",
                    }
                ]
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
                *extra,
            ]
            place = geo.get(ip)
            if place and place[0]:
                where = f"{place[0]}" + (f", AS{place[1]} {place[2]}" if place[1] else "")
                reasons.append(
                    {
                        "family": "NET",
                        "feature": "geoip",
                        "value": place[0],
                        "contribution": 0.0,
                        "text": f"GeoIP places this IP in {where} (DB-IP Lite, 2026-09). Location context only; it does not change the score.",
                    }
                )
            out.append(
                (
                    lead_key("ACTOR", "ip_cluster", subject),
                    "ACTOR",
                    "ip_cluster",
                    subject,
                    round(p, 4),
                    grade,
                    round(p * (1 + math.log10(1 + int(value) / 1e8)), 4),
                    json.dumps(families),
                    json.dumps(reasons),
                    int(value),
                    int(last_us) if last_us is not None else None,
                    f"IP {ip} likely operates wallet cluster {cluster_id[:10]}",
                    f"Evidence suggests {ip} may be the network origin of {n_tx} transaction(s) from a {n_addr}-address wallet cluster. This is a lead for review, not proof of identity.",
                )
            )
        out += _chain_leads(con, have) + _anomaly_leads(con, have) + _taint_leads(con, have, taint_of)
        out.sort(key=lambda r: (-r[6], r[0]))
        if out:
            con.executemany(
                "INSERT INTO lead VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(i, *r, False, "evidence", MODEL_VERSION, ctx.run_id) for i, r in enumerate(out)],
            )
        return StageReport(rows={"lead": len(out)})


STAGE = RankStage()
