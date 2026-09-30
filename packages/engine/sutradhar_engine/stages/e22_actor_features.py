"""E22 actor features - one row per active wallet cluster, ~36 features for the lead ranker.

Built from the ledger, the network observations and the earlier stages (clusters, flows, motifs, taint, risk,
origin, anomaly). Also fits an Isolation Forest over the behavioural features and stores each actor's percentile
as `actor_anom` (P5.4). Nothing here can see ground truth.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from sutradhar_engine.actor_model import FEATURES
from sutradhar_engine.runner import RunContext, StageReport

BEHAV_FOR_ANOM = (
    "log_n_addr",
    "log_tx_sent",
    "log_tx_recv",
    "log_counterparties",
    "avg_n_in",
    "avg_n_out",
    "log_sent",
    "log_recv",
    "log_lifetime_h",
    "consolidation_share",
    "fan_out_share",
    "log_fee_rate",
    "log_gap_h",
    "night_share",
)

BASE_SQL = """
CREATE TEMP TABLE tx_actor AS
SELECT i.txid, min(c.cluster_id) AS cluster_id FROM ds.txin i JOIN cluster c USING (address) GROUP BY i.txid;

CREATE TEMP TABLE txf AS
SELECT a.cluster_id, t.txid, t.n_in, t.n_out, t.fee_sats, t.first_seen_us, t.in_sats,
       (m.kind = 'consolidation')::INT AS is_cons, (m.kind = 'fan_out')::INT AS is_fan,
       (cj.txid IS NOT NULL)::INT AS is_cj, (pc.txid IS NOT NULL)::INT AS in_peel,
       coalesce(an.score, 0) AS anom, o.ip AS top_ip, coalesce(o.p, 0) AS top_p
FROM tx_actor a JOIN ds.tx t USING (txid)
LEFT JOIN motif m USING (txid)
LEFT JOIN (SELECT txid FROM coinjoin WHERE p >= 0.5) cj USING (txid)
LEFT JOIN (SELECT DISTINCT txid FROM peel_chain) pc USING (txid)
LEFT JOIN anomaly an USING (txid)
LEFT JOIN (SELECT txid, ip, p FROM origin WHERE rnk = 1) o USING (txid);

CREATE TEMP TABLE agg AS
SELECT cluster_id, count(*) AS n, avg(is_cons) AS cons, avg(is_fan) AS fan, avg(is_cj) AS cj, avg(in_peel) AS peel,
       max(anom) AS anom_max, avg(anom) AS anom_mean,
       median(fee_sats * 1.0 / (68 * n_in + 31 * n_out + 11)) AS feerate,
       avg(CASE WHEN ((first_seen_us / 3600000000) % 24) < 6 THEN 1.0 ELSE 0.0 END) AS night,
       avg(CASE WHEN top_ip IS NULL OR top_p < 0.3 THEN 1.0 ELSE 0.0 END) AS unobs,
       avg(CASE WHEN top_p >= 0.3 THEN top_p END) AS mean_p,
       count(DISTINCT CASE WHEN top_p >= 0.3 THEN top_ip END) AS n_ips
FROM txf GROUP BY 1;

CREATE TEMP TABLE ipshare AS
SELECT cluster_id, max(k) * 1.0 / sum(k) AS top_share FROM (
  SELECT cluster_id, top_ip, count(*) AS k FROM txf WHERE top_p >= 0.3 GROUP BY 1, 2) GROUP BY 1;

CREATE TABLE actor_ip AS
SELECT cluster_id, top_ip AS ip, count(*)::INTEGER AS n_tx, avg(top_p) AS mean_p FROM txf WHERE top_p >= 0.3 GROUP BY 1, 2;

CREATE TEMP TABLE gaps AS
SELECT cluster_id, median(gap) AS gap_us FROM (
  SELECT cluster_id, first_seen_us - lag(first_seen_us) OVER (PARTITION BY cluster_id ORDER BY first_seen_us) AS gap FROM txf)
WHERE gap IS NOT NULL GROUP BY 1;

CREATE TEMP TABLE chainlen AS
SELECT t.cluster_id, max(cl.n) AS peel_len FROM txf t JOIN peel_chain p USING (txid)
JOIN (SELECT chain_id, count(*) AS n FROM peel_chain GROUP BY 1) cl USING (chain_id) GROUP BY 1;

CREATE TEMP TABLE flows AS
SELECT c, sum(CASE WHEN dir = 'out' THEN sats ELSE 0 END) AS out_sats, sum(CASE WHEN dir = 'in' THEN sats ELSE 0 END) AS in_sats,
       sum(CASE WHEN dir = 'out' AND o_svc THEN sats ELSE 0 END) AS out_svc, sum(CASE WHEN dir = 'in' AND o_svc THEN sats ELSE 0 END) AS in_svc,
       sum(CASE WHEN dir = 'in' THEN sats * o_taint ELSE 0 END) AS in_taint FROM (
  SELECT f.src AS c, 'out' AS dir, f.sats, (f.dst IN (SELECT cluster_id FROM service)) AS o_svc, 0.0 AS o_taint FROM flow f
  UNION ALL
  SELECT f.dst, 'in', f.sats, (f.src IN (SELECT cluster_id FROM service)), coalesce(r.taint, 0.0) FROM flow f LEFT JOIN cluster_risk r ON r.cluster_id = f.src
) GROUP BY 1;

CREATE TEMP TABLE shared AS
SELECT c, count(*) AS n FROM (SELECT a AS c FROM co_origin UNION ALL SELECT b FROM co_origin) GROUP BY 1;

CREATE TEMP TABLE countries AS
SELECT t.cluster_id, count(DISTINCT g.country) AS n FROM txf t JOIN ip_geo g ON g.ip = t.top_ip WHERE t.top_p >= 0.3 GROUP BY 1;

CREATE TEMP TABLE paths AS SELECT target AS cluster_id, count(*) AS n FROM risk_path GROUP BY 1;
"""

FINAL_SQL = """
SELECT s.cluster_id,
  ln(1 + s.n_addr) AS log_n_addr, ln(1 + s.n_tx_sent) AS log_tx_sent, ln(1 + s.n_tx_recv) AS log_tx_recv,
  ln(1 + s.n_counterparties) AS log_counterparties, s.avg_n_in, s.avg_n_out,
  ln(1 + s.sent_sats / 1e6) AS log_sent, ln(1 + s.recv_sats / 1e6) AS log_recv,
  ln(1 + coalesce((s.last_us - s.first_us) / 3.6e9, 0)) AS log_lifetime_h,
  coalesce(a.cons, 0) AS consolidation_share, coalesce(a.fan, 0) AS fan_out_share, coalesce(a.cj, 0) AS coinjoin_share,
  coalesce(a.peel, 0) AS peel_share, coalesce(cl.peel_len, 0) AS peel_len_max,
  coalesce(f.out_svc * 1.0 / nullif(f.out_sats, 0), 0) AS out_service_share,
  coalesce(f.in_svc * 1.0 / nullif(f.in_sats, 0), 0) AS in_service_share,
  coalesce(r.taint, 0) AS taint_max, coalesce(f.in_taint * 1.0 / nullif(f.in_sats, 0), 0) AS taint_in_frac,
  log10(1 + coalesce(r.ppr, 0) * 10000) AS ppr_log, coalesce(least(r.hops, 9), 9) AS seed_hops,
  least(coalesce(p.n, 0), 3) AS n_risk_paths,
  coalesce(ip.top_share, 0) AS top_ip_share, coalesce(a.n_ips, 0) AS n_origin_ips, coalesce(a.mean_p, 0) AS mean_origin_p,
  coalesce(a.unobs, 1) AS unobservable_share, ln(1 + coalesce(sh.n, 0)) AS log_shared_ip_clusters,
  coalesce(co.n, 0) AS country_count,
  coalesce(a.anom_max, 0) AS tx_anom_max, coalesce(a.anom_mean, 0) AS tx_anom_mean,
  ln(1 + coalesce(a.feerate, 0)) AS log_fee_rate, ln(1 + coalesce(g.gap_us / 3.6e9, 0)) AS log_gap_h,
  coalesce(a.night, 0) AS night_share, coalesce(v.exposure_out, 0) AS victim_exposure,
  coalesce(sv.score, 0) AS service_score, (ca.cluster_id IS NOT NULL)::INT AS is_cashout
FROM cluster_stats s
LEFT JOIN agg a USING (cluster_id) LEFT JOIN ipshare ip USING (cluster_id) LEFT JOIN gaps g USING (cluster_id)
LEFT JOIN chainlen cl USING (cluster_id) LEFT JOIN flows f ON f.c = s.cluster_id LEFT JOIN shared sh ON sh.c = s.cluster_id
LEFT JOIN countries co USING (cluster_id) LEFT JOIN paths p USING (cluster_id) LEFT JOIN cluster_risk r USING (cluster_id)
LEFT JOIN victim v USING (cluster_id) LEFT JOIN service sv USING (cluster_id)
LEFT JOIN (SELECT DISTINCT cluster_id FROM cashout) ca USING (cluster_id)
WHERE s.n_tx_sent >= 1 OR coalesce(r.taint, 0) > 0
ORDER BY s.cluster_id
"""


def _ensure_optional(con) -> None:  # type: ignore[no-untyped-def]
    """Chain-only datasets have no network stages; give the SQL empty stand-ins so the features are just zeros."""
    have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    if "origin" not in have:
        con.execute(
            "CREATE TABLE origin (txid VARCHAR, ip VARCHAR, p DOUBLE, rnk INTEGER, sensors_heard INTEGER, sensors_first INTEGER)"
        )
    if "co_origin" not in have:
        con.execute("CREATE TABLE co_origin (a VARCHAR, b VARCHAR, shared_ips INTEGER, shared_tx INTEGER)")
    if "ip_geo" not in have:
        con.execute(
            "CREATE TABLE ip_geo (ip VARCHAR, country VARCHAR, asn BIGINT, org VARCHAR, note VARCHAR, source VARCHAR, as_of VARCHAR)"
        )


class ActorFeatureStage:
    code = "E22"
    name = "actor features"
    requires = (
        "cluster_stats",
        "cluster_risk",
        "victim",
        "risk_path",
        "cashout",
        "motif",
        "coinjoin",
        "anomaly",
    )
    produces = ("actor_features", "actor_ip")

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        _ensure_optional(con)
        for statement in [s for s in BASE_SQL.split(";") if s.strip()]:
            con.execute(statement)
        rows = con.execute(FINAL_SQL).fetchall()
        names = [d[0] for d in con.description][1:]
        ids = [r[0] for r in rows]
        matrix = np.array([[float(v or 0.0) for v in r[1:]] for r in rows], dtype=float).reshape(
            len(rows), len(names)
        )
        idx = {n: i for i, n in enumerate(names)}
        anom = np.zeros(len(rows))
        if len(rows) >= 30:
            sub = matrix[:, [idx[n] for n in BEHAV_FOR_ANOM]]
            sd = sub.std(axis=0)
            sd[sd == 0] = 1.0
            forest = IsolationForest(n_estimators=200, random_state=ctx.settings.seed, n_jobs=1).fit(
                (sub - sub.mean(axis=0)) / sd
            )
            raw = -forest.score_samples((sub - sub.mean(axis=0)) / sd)
            anom = raw.argsort().argsort() / max(1, len(raw) - 1)
        columns = {n: matrix[:, i] for n, i in idx.items()}
        columns["actor_anom"] = anom
        cols_sql = ", ".join(f'"{f}" DOUBLE NOT NULL' for f in FEATURES)
        con.execute(f"CREATE TABLE actor_features (cluster_id VARCHAR PRIMARY KEY, {cols_sql})")  # nosec B608
        if ids:
            placeholders = ", ".join(["?"] * (len(FEATURES) + 1))
            con.executemany(
                f"INSERT INTO actor_features VALUES ({placeholders})",  # noqa: S608  # nosec B608
                [[ids[i], *[float(columns[f][i]) for f in FEATURES]] for i in range(len(ids))],
            )
        return StageReport(rows={"actor_features": len(ids)}, notes=[f"{len(FEATURES)} features"])


STAGE = ActorFeatureStage()
