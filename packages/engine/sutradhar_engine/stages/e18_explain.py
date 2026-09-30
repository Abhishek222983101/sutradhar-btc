"""E18 explain - reasons, opposing evidence, counterfactuals, priority breakdown, drift and a hedged summary per lead."""

from __future__ import annotations

import json

import numpy as np

from sutradhar_engine.actor_model import FEATURE_FAMILY, FEATURES, Ranker
from sutradhar_engine.explain.counterfactual import counterfactuals
from sutradhar_engine.explain.drift import drift_report
from sutradhar_engine.explain.guard import check_summary
from sutradhar_engine.explain.render import hedged_summary, render_reason
from sutradhar_engine.runner import RunContext, StageReport

FEATURE_SELECT = "SELECT cluster_id, " + ", ".join(FEATURES) + " FROM actor_features"  # noqa: S608  # nosec B608 - constant names
PHRASE = {
    "TAINT": "receives funds traced to watchlisted wallets",
    "NET": "is probably operated from one IP address",
    "FLOW": "moves money in a peeling or sweeping pattern",
    "ANOM": "behaves unusually compared with the rest of the data",
    "BEHAV": "shows an automated-looking payment rhythm",
}
SHORT = {
    "TAINT": "traced funds",
    "NET": "single-IP operation",
    "FLOW": "fund-spreading pattern",
    "ANOM": "unusual behaviour",
    "BEHAV": "automated rhythm",
}


class ExplainStage:
    code = "E18"
    name = "explanations"
    requires = ("lead", "actor_scores")
    produces = ("explain_meta",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        ranker = Ranker()
        feats = {r[0]: np.array(r[1:], dtype=float) for r in con.execute(FEATURE_SELECT).fetchall()}
        contrib = {
            r[0]: np.array(json.loads(r[1]))
            for r in con.execute("SELECT cluster_id, contrib FROM actor_scores").fetchall()
        }
        drift = (
            drift_report(ranker.meta, np.array(list(feats.values())))
            if feats
            else {"level": "none", "max_psi": 0.0, "shifted": []}
        )
        provenance = {
            "model": ranker.version,
            "calibrated": True,
            "drift": drift,
        }  # no run id: digests must not depend on it
        geo = (
            {
                r[0]: (r[1], r[2], r[3])
                for r in con.execute("SELECT ip, country, asn, org FROM ip_geo").fetchall()
            }
            if _has(con, "ip_geo")
            else {}
        )
        n = 0
        for lead_i, ltype, ref, explain_json, families_json in con.execute(
            "SELECT lead_i, type, subject_ref, explain, families FROM lead ORDER BY lead_i"
        ).fetchall():
            explain = json.loads(explain_json)
            families = json.loads(families_json)
            explain["provenance"] = provenance
            if ltype == "ACTOR":
                x, c = feats[ref], contrib[ref]
                order = np.argsort(-c[:-1])
                reasons = [r for j in order if c[j] > 0.05 and (r := render_reason(FEATURES[j], x[j], c[j]))][
                    :5
                ]
                opposing = [
                    r for j in order[::-1] if c[j] < -0.05 and (r := render_reason(FEATURES[j], x[j], c[j]))
                ][:2]
                if (
                    not reasons
                ):  # a lead always shows at least one reason (I6): fall back to the strongest detector hit
                    j = int(np.argmax(np.abs(c[:-1])))
                    reasons = [r for r in [render_reason(FEATURES[j], x[j], abs(c[j]))] if r]
                explain["opposing"] = opposing
                explain["counterfactual"] = counterfactuals(ranker, x, c)
                fam_sum = explain.get("fam_sum", {})
                lead_fams = sorted(families, key=lambda f: -fam_sum.get(f, 0))
                core = PHRASE[lead_fams[0]] if lead_fams else "may deserve a closer look"
                title = f"Wallet group {ref[:10]}…: " + " and ".join(SHORT[f] for f in lead_fams[:2])
                summary = hedged_summary(f"this wallet group {core}", len(families))
                top_ip = con.execute(
                    "SELECT ip FROM actor_ip WHERE cluster_id = ? ORDER BY n_tx DESC, ip LIMIT 1", [ref]
                ).fetchone()
                if top_ip and top_ip[0] in geo and geo[top_ip[0]][0]:
                    cc, asn, org = geo[top_ip[0]]
                    reasons.append(
                        {
                            "family": "NET",
                            "feature": "geoip",
                            "label": "Where the IP is",
                            "value": cc,
                            "contribution": 0.0,
                            "text": f"GeoIP places its most likely origin IP {top_ip[0]} in {cc}"
                            + (f" (AS{asn} {org})" if asn else "")
                            + ". This is location context only and does not change the score.",
                        }
                    )
                con.execute(
                    "UPDATE lead SET reasons = ?, explain = ?, title = ?, summary = ? WHERE lead_i = ?",
                    [json.dumps(reasons), json.dumps(explain), title, summary, lead_i],
                )
            elif ltype == "CASHOUT":
                cid, service = ref.split("|")
                share, taint = (
                    explain.get("share", 0),
                    con.execute(
                        "SELECT taint FROM cashout WHERE cluster_id = ? AND service_id = ?", [cid, service]
                    ).fetchone(),
                )
                reasons = [
                    {
                        "family": "FLOW",
                        "feature": "out_service_share",
                        "label": "Sends to an exchange",
                        "value": share,
                        "contribution": round(share, 3),
                        "text": f"{share * 100:.0f}% of what this wallet group sent went to one exchange-like service, where funds can be cashed out.",
                    },
                    {
                        "family": "TAINT",
                        "feature": "taint_max",
                        "label": "Traced funds",
                        "value": round(float(taint[0]), 3) if taint else 0,
                        "contribution": 0.5,
                        "text": "The funds it holds can be traced back to a watchlisted wallet.",
                    },
                ]
                explain["counterfactual"] = []
                con.execute(
                    "UPDATE lead SET reasons = ?, explain = ?, title = ?, summary = ? WHERE lead_i = ?",
                    [
                        json.dumps(reasons),
                        json.dumps(explain),
                        f"Possible cash-out by wallet group {cid[:10]}…",
                        hedged_summary("this wallet group may be cashing out traced funds at an exchange", 2),
                        lead_i,
                    ],
                )
            elif ltype == "IP":
                linked = explain.get("linked", [])
                place = geo.get(ref)
                reasons = [
                    {
                        "family": "NET",
                        "feature": "shared_ip",
                        "label": "One IP, several wallets",
                        "value": len(linked),
                        "contribution": round(0.2 * len(linked), 3),
                        "text": f"{len(linked)} flagged wallet groups appear to be operated from this same IP address.",
                    }
                ]
                if place and place[0]:
                    reasons.append(
                        {
                            "family": "NET",
                            "feature": "geoip",
                            "label": "Where the IP is",
                            "value": place[0],
                            "contribution": 0.0,
                            "text": f"GeoIP places it in {place[0]}"
                            + (f" (AS{place[1]} {place[2]})" if place[1] else "")
                            + "; location context only.",
                        }
                    )
                con.execute(
                    "UPDATE lead SET reasons = ?, explain = ?, title = ?, summary = ? WHERE lead_i = ?",
                    [
                        json.dumps(reasons),
                        json.dumps(explain),
                        f"IP {ref} appears behind {len(linked)} flagged wallet groups",
                        hedged_summary(
                            f"one IP address ({ref}) may be behind {len(linked)} wallet groups", 1
                        ),
                        lead_i,
                    ],
                )
            else:
                check_summary(
                    con.execute("SELECT summary FROM lead WHERE lead_i = ?", [lead_i]).fetchone()[0]
                )
                con.execute("UPDATE lead SET explain = ? WHERE lead_i = ?", [json.dumps(explain), lead_i])
            n += 1
        con.execute("CREATE TABLE explain_meta (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        con.executemany(
            "INSERT INTO explain_meta VALUES (?, ?)",
            [("model", ranker.version), ("drift", json.dumps(drift)), ("leads", str(n))],
        )
        return StageReport(
            rows={"explained": n}, notes=[f"drift: {drift['level']} (max PSI {drift['max_psi']})"]
        )


def _has(con, table: str) -> bool:  # type: ignore[no-untyped-def]
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
        ).fetchone()[0]
    )


STAGE = ExplainStage()
_ = FEATURE_FAMILY
