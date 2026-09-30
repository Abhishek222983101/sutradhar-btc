"""E17 rank - turn actor features into calibrated, graded, prioritised leads (five lead types).

ACTOR   a wallet cluster scored by the trained lead ranker (LightGBM) and calibrated (isotonic).
CASHOUT a flagged cluster moving traced funds into an exchange-like service.
CHAIN   a peeling chain.   TX  a statistically unusual transaction.   IP  an address behind several flagged actors.

Grade uses *independent evidence families*, not just the score: A needs p >= 0.8 and three families; B needs
p >= 0.5 and two; everything else is C. Services and victims never become ACTOR leads. `explain` is filled by E18.
"""

from __future__ import annotations

import json
import math

import numpy as np

from sutradhar_engine.actor_model import FAMILIES, FEATURE_FAMILY, FEATURES, Ranker, available
from sutradhar_engine.runner import RunContext, RunError, StageReport
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
    run_id             VARCHAR NOT NULL,
    explain            JSON    NOT NULL DEFAULT '{}'
)
"""
INSERT_SQL = "INSERT INTO lead VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"


def lead_key(lead_type: str, subject_kind: str, subject_ref: str) -> str:
    return sha256_hex(f"{lead_type}|{subject_kind}|{subject_ref}")[:16]


def grade_for(p: float, n_families: int) -> str:
    if p >= 0.8 and n_families >= 3:
        return "A"
    return "B" if p >= 0.5 and n_families >= 2 else "C"


def priority_parts(
    p: float, recv_btc: float, days_idle: float, actionable: bool, half_life: float
) -> dict[str, float]:
    """priority = p x value x recency x actionable (each factor is reported with the lead)."""
    return {
        "p": round(p, 4),
        "value_factor": round(1 + math.log10(1 + max(recv_btc, 0.0)), 4),
        "recency_factor": round(0.5 ** (max(days_idle, 0.0) / half_life), 4),
        "actionable_factor": 1.25 if actionable else 1.0,
    }


def priority_of(parts: dict[str, float]) -> float:
    return round(parts["p"] * parts["value_factor"] * parts["recency_factor"] * parts["actionable_factor"], 4)


def detector_families(f: dict[str, float]) -> set[str]:
    """Independent hits that count as evidence even when the model's contribution for the family is small."""
    hits = set()
    if f["top_ip_share"] >= 0.5 and f["mean_origin_p"] >= 0.3 and f["n_origin_ips"] >= 1:
        hits.add("NET")
    if f["peel_len_max"] >= 3 or f["is_cashout"] >= 1 or f["coinjoin_share"] >= 0.3:
        hits.add("FLOW")
    if f["taint_max"] >= 0.05:
        hits.add("TAINT")
    if f["tx_anom_max"] >= 0.98:
        hits.add("ANOM")
    return hits


class RankStage:
    code = "E17"
    name = "rank leads"
    requires = ("actor_features",)
    produces = ("lead", "actor_scores")

    def run(self, ctx: RunContext) -> StageReport:
        con, s = ctx.con, ctx.settings
        if not available():
            raise RunError("E17", "the lead ranker is not trained; run `sutradhar evals train-ranker`")
        ranker = Ranker()
        con.execute(LEAD_DDL)
        cols = ["cluster_id", *FEATURES]
        rows = con.execute(f"SELECT {', '.join(cols)} FROM actor_features ORDER BY cluster_id").fetchall()  # noqa: S608  # nosec B608
        ids = [r[0] for r in rows]
        x = np.array([[float(v) for v in r[1:]] for r in rows], dtype=float).reshape(len(rows), len(FEATURES))
        prob = ranker.prob(x) if len(rows) else np.zeros(0)
        contrib = ranker.contributions(x) if len(rows) else np.zeros((0, len(FEATURES) + 1))
        con.execute(
            "CREATE TABLE actor_scores (cluster_id VARCHAR PRIMARY KEY, p DOUBLE NOT NULL, contrib VARCHAR NOT NULL)"
        )
        if rows:
            con.executemany(
                "INSERT INTO actor_scores VALUES (?, ?, ?)",
                [
                    (ids[i], float(prob[i]), json.dumps([round(float(v), 5) for v in contrib[i]]))
                    for i in range(len(ids))
                ],
            )
        excluded = {
            r[0]
            for r in con.execute(
                "SELECT cluster_id FROM service UNION SELECT cluster_id FROM victim"
            ).fetchall()
        }
        stats = {
            r[0]: r[1:]
            for r in con.execute("SELECT cluster_id, recv_sats, last_us FROM cluster_stats").fetchall()
        }
        span_end = con.execute("SELECT coalesce(max(last_us), 0) FROM cluster_stats").fetchone()[0] or 0
        seed_clusters = dict(
            con.execute(
                "SELECT DISTINCT c.cluster_id, t.category FROM taint t JOIN cluster c USING (address) WHERE t.is_seed"
            ).fetchall()
        )
        leads: list[tuple] = []
        actor_p: dict[str, float] = {}
        for i, cid in enumerate(ids):
            if cid in excluded or prob[i] < s.lead_min_p:
                continue
            f = dict(zip(FEATURES, x[i], strict=True))
            fam_sum = {
                fam: sum(contrib[i][j] for j, n in enumerate(FEATURES) if FEATURE_FAMILY[n] == fam)
                for fam in FAMILIES
            }
            families = sorted(
                {fam for fam, v in fam_sum.items() if v >= s.family_min_contrib} | detector_families(f)
            )
            if not families:
                continue
            recv_sats, last_us = stats.get(cid, (0, None))
            days_idle = (span_end - (last_us or span_end)) / 8.64e10
            actionable = (f["n_origin_ips"] >= 1 and f["mean_origin_p"] >= 0.3) or f["is_cashout"] >= 1
            parts = priority_parts(
                float(prob[i]), int(recv_sats) / 1e8, days_idle, actionable, s.recency_halflife_days
            )
            actor_p[cid] = float(prob[i])
            leads.append(
                (
                    "ACTOR",
                    "cluster",
                    cid,
                    round(float(prob[i]), 4),
                    grade_for(float(prob[i]), len(families)),
                    priority_of(parts),
                    families,
                    [],
                    int(recv_sats),
                    last_us,
                    "",
                    "",
                    True,
                    "lgbm+isotonic",
                    ranker.version,
                    {
                        "priority": parts,
                        "fam_sum": {k: round(float(v), 3) for k, v in fam_sum.items()},
                        **({"seed_hit": seed_clusters[cid] or "watchlist"} if cid in seed_clusters else {}),
                    },
                )
            )
        leads += self._cashout_leads(con, actor_p, ranker.version, stats)
        leads += self._ip_leads(con, actor_p, ranker.version)
        leads += self._chain_leads(con, actor_p)
        leads += self._tx_leads(con)
        leads.sort(key=lambda r: (-r[5], r[0], r[2]))
        leads = leads[: s.lead_limit]
        if leads:
            con.executemany(
                INSERT_SQL,
                [
                    (
                        i,
                        lead_key(r[0], r[1], r[2]),
                        r[0],
                        r[1],
                        r[2],
                        r[3],
                        r[4],
                        r[5],
                        json.dumps(r[6]),
                        json.dumps(r[7]),
                        r[8],
                        r[9],
                        r[10],
                        r[11],
                        r[12],
                        r[13],
                        r[14],
                        ctx.run_id,
                        json.dumps(r[15]),
                    )
                    for i, r in enumerate(leads)
                ],
            )
        by_type: dict[str, int] = {}
        for r in leads:
            by_type[r[0]] = by_type.get(r[0], 0) + 1
        return StageReport(
            rows={"lead": len(leads), **{f"lead_{k.lower()}": v for k, v in sorted(by_type.items())}}
        )

    # ── other lead types ──
    @staticmethod
    def _cashout_leads(con, actor_p: dict[str, float], version: str, stats: dict) -> list[tuple]:  # type: ignore[no-untyped-def]
        out = []
        for cid, service, sats, share, taint in con.execute(
            "SELECT cluster_id, service_id, sats, share, taint FROM cashout ORDER BY 1, 2"
        ).fetchall():
            base = actor_p.get(cid, 0.0)
            p = round(min(0.95, base * share + 0.05 * min(1.0, taint * 10)), 4)
            if p < 0.1:
                continue
            last = stats.get(cid, (0, None))[1]
            parts = priority_parts(p, int(sats) / 1e8, 0.0, True, 30.0)
            out.append(
                (
                    "CASHOUT",
                    "cashout",
                    f"{cid}|{service}",
                    p,
                    "B" if p >= 0.5 else "C",
                    priority_of(parts),
                    ["FLOW", "TAINT"],
                    [],
                    int(sats),
                    last,
                    "",
                    "",
                    True,
                    "cashout-from-actor",
                    version,
                    {"priority": parts, "share": share},
                )
            )
        return out

    @staticmethod
    def _ip_leads(con, actor_p: dict[str, float], version: str) -> list[tuple]:  # type: ignore[no-untyped-def]
        by_ip: dict[str, list[tuple[str, float, int]]] = {}
        for cid, ip, n_tx, _mean_p in con.execute(
            "SELECT cluster_id, ip, n_tx, mean_p FROM actor_ip ORDER BY 1, 2"
        ).fetchall():
            if cid in actor_p and actor_p[cid] >= 0.3:
                by_ip.setdefault(ip, []).append((cid, actor_p[cid], int(n_tx)))
        out = []
        for ip, linked in sorted(by_ip.items()):
            if len(linked) < 2:
                continue
            p = round(1 - math.prod(1 - 0.7 * lp for _, lp, _ in linked), 4)
            parts = priority_parts(p, 0.0, 0.0, True, 30.0)
            out.append(
                (
                    "IP",
                    "ip",
                    ip,
                    p,
                    "B" if p >= 0.5 else "C",
                    priority_of(parts),
                    ["NET"],
                    [],
                    0,
                    None,
                    "",
                    "",
                    True,
                    "noisy-or",
                    version,
                    {"priority": parts, "linked": [c for c, _, _ in linked]},
                )
            )
        return out

    @staticmethod
    def _chain_leads(con, actor_p: dict[str, float]) -> list[tuple]:  # type: ignore[no-untyped-def]
        """A peeling chain is only as suspicious as the wallet running it: the rule's score is blended with the owner's
        ranker score, so fast sequential payers that merely look like a chain (bots, payroll) fall away."""
        owner = dict(
            con.execute(
                "SELECT p.chain_id, min(c.cluster_id) FROM peel_chain p JOIN ds.txin i USING (txid) JOIN cluster c USING (address) GROUP BY 1"
            ).fetchall()
        )
        out = []
        for chain_id, hops, value, last, first in con.execute(
            "SELECT chain_id, count(*), sum(remainder_sats), max(ts_us), min(txid) FROM peel_chain GROUP BY 1 ORDER BY 1"
        ).fetchall():
            rule = min(0.7, 0.35 + 0.08 * hops)
            p = round(0.25 * rule + 0.75 * actor_p.get(owner.get(chain_id, ""), 0.0), 4)
            if p < 0.2:
                continue
            parts = priority_parts(p, int(value) / 1e8, 0.0, False, 30.0)
            reasons = [
                {
                    "family": "FLOW",
                    "feature": "peel_hops",
                    "label": "Peeling chain",
                    "value": hops,
                    "contribution": round(0.08 * hops, 3),
                    "text": f"{hops} consecutive payments each send a small amount out and pass the remainder on, a pattern used to spread funds quickly.",
                }
            ]
            out.append(
                (
                    "CHAIN",
                    "chain",
                    chain_id,
                    p,
                    "B" if p >= 0.5 else "C",
                    priority_of(parts),
                    ["FLOW"],
                    reasons,
                    int(value),
                    int(last),
                    f"Peeling chain of {hops} steps",
                    f"Evidence suggests {hops} payments starting at transaction {first[:10]} may be one chain that spreads funds. Lead for review, not a finding about anyone.",
                    False,
                    "peel-traversal+owner",
                    "rules@2",
                    {"priority": parts, "owner": owner.get(chain_id)},
                )
            )
        return out

    @staticmethod
    def _tx_leads(con) -> list[tuple]:  # type: ignore[no-untyped-def]
        out = []
        for txid, score, sats, n_in, n_out, ts in con.execute(
            "SELECT a.txid, a.score, x.in_sats, x.n_in, x.n_out, x.first_seen_us FROM anomaly a JOIN ds.tx x USING (txid) "
            "WHERE a.score >= 0.985 ORDER BY a.score DESC, a.txid LIMIT 8"
        ).fetchall():
            p = round(0.2 + 0.2 * (score - 0.985) / 0.015, 4)
            parts = priority_parts(p, int(sats) / 1e8, 0.0, False, 30.0)
            reasons = [
                {
                    "family": "ANOM",
                    "feature": "isolation_score",
                    "label": "Unusual payment",
                    "value": round(score, 3),
                    "contribution": round(score, 3),
                    "text": f"A model rates this payment ({n_in} inputs, {n_out} outputs) as more unusual than {score * 100:.0f}% of the payments in the data.",
                }
            ]
            out.append(
                (
                    "TX",
                    "tx",
                    txid,
                    p,
                    "C",
                    priority_of(parts),
                    ["ANOM"],
                    reasons,
                    int(sats),
                    int(ts),
                    f"Unusual payment {txid[:10]}",
                    "Evidence suggests the shape of this payment (value, fee, split) is atypical for this data. Unusual does not mean illicit; treat it as a lead for review.",
                    False,
                    "isolation-forest",
                    "iforest@1",
                    {"priority": parts},
                )
            )
        return out


STAGE = RankStage()
