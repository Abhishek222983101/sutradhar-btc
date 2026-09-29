"""I06 — capability profile ("Dataset X-ray"): what this dataset lets the engine do, and why.

Computed with SQL over the finished dataset store so it is cheap and always consistent with the data.
"""

from __future__ import annotations

import duckdb

from sutradhar_schemas.enums import ObservationModel
from sutradhar_schemas.evidence import CapabilityProfile, NetworkCapability

ALL_STAGES = [f"E{i:02d}" for i in range(1, 20)]
NET_STAGES = ("E09", "E10", "E11")


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> float:
    value = con.execute(sql).fetchone()
    return 0.0 if value is None or value[0] is None else float(value[0])


def detect_observation_model(
    has_network: bool, obs_per_tx_p90: float, sensor_row_share: float, n_sensors: int, distinct_dst: int
) -> ObservationModel:
    """Vantage: a few destinations (sensors) hear most transactions and carry almost every row.
    Flow: records spread over many destinations, each hearing few transactions. Mixed: both present."""
    if not has_network:
        return ObservationModel.NONE
    if obs_per_tx_p90 <= 1:
        return ObservationModel.SINGLE
    if n_sensors and sensor_row_share >= 0.9:
        return ObservationModel.VANTAGE
    if n_sensors and sensor_row_share >= 0.3:
        return ObservationModel.MIXED
    if distinct_dst > 0:
        return ObservationModel.FLOW
    return ObservationModel.NONE


SENSOR_COVERAGE = 0.30  # a destination hearing at least this share of all transactions is a sensor


def build_capability(
    con: duckdb.DuckDBPyConnection,
    *,
    amount_unit: dict[str, object],
    rejects: int,
    duplicates: int,
    source_rows: int,
    conflicts: int,
) -> CapabilityProfile:
    rows = int(_scalar(con, "SELECT count(*) FROM obs"))
    txs = int(_scalar(con, "SELECT count(*) FROM tx"))
    addresses = int(
        _scalar(
            con,
            "SELECT count(DISTINCT address) FROM (SELECT address FROM txin UNION ALL SELECT address FROM txout)",
        )
    )
    ips = int(
        _scalar(
            con,
            "SELECT count(DISTINCT ip) FROM (SELECT src_ip AS ip FROM obs UNION ALL SELECT dst_ip FROM obs) WHERE ip IS NOT NULL",
        )
    )
    distinct_src = int(_scalar(con, "SELECT count(DISTINCT src_ip) FROM obs"))
    distinct_dst = int(_scalar(con, "SELECT count(DISTINCT dst_ip) FROM obs"))
    has_network = distinct_src > 0
    dst_8333 = _scalar(
        con, "SELECT avg(CASE WHEN dst_port = 8333 THEN 1.0 ELSE 0.0 END) FROM obs WHERE dst_port IS NOT NULL"
    )
    p50 = _scalar(con, "SELECT quantile_cont(n, 0.5) FROM (SELECT count(*) n FROM obs GROUP BY txid)")
    p90 = _scalar(con, "SELECT quantile_cont(n, 0.9) FROM (SELECT count(*) n FROM obs GROUP BY txid)")
    coverage = con.execute(
        """
        SELECT dst_ip, count(DISTINCT txid) * 1.0 / (SELECT count(*) FROM tx) AS cov, count(*) AS n
        FROM obs WHERE dst_ip IS NOT NULL GROUP BY dst_ip
        """
    ).fetchall()
    sensor_rows = sum(n for _, cov, n in coverage if cov >= SENSOR_COVERAGE)
    n_sensors = sum(1 for _, cov, _ in coverage if cov >= SENSOR_COVERAGE)
    sensor_row_share = sensor_rows / rows if rows else 0.0
    model = detect_observation_model(has_network, p90, sensor_row_share, n_sensors, distinct_dst)
    span = con.execute("SELECT min(ts_us), max(ts_us) FROM obs").fetchone() or (None, None)
    fee_provided = _scalar(con, "SELECT avg(CASE WHEN fee_src = 'provided' THEN 1.0 ELSE 0.0 END) FROM tx")
    unknown_scripts = _scalar(
        con,
        "SELECT avg(CASE WHEN script_type = 'unknown' THEN 1.0 ELSE 0.0 END) FROM (SELECT script_type FROM txin UNION ALL SELECT script_type FROM txout)",
    )
    sensors = n_sensors if model in (ObservationModel.VANTAGE, ObservationModel.MIXED) else 0

    disabled: list[str] = []
    warnings: list[str] = []
    stages = list(ALL_STAGES)
    if model == ObservationModel.NONE:
        stages = [s for s in stages if s not in NET_STAGES]
        disabled.append("network correlation (no src/dst IP and port fields)")
    if model == ObservationModel.SINGLE:
        warnings.append("one record per transaction: origins are taken as reported, not inferred")
    if unknown_scripts > 0.5:
        disabled.append("script-type features (addresses are not standard Bitcoin forms)")
    if conflicts:
        warnings.append(f"{conflicts} transaction id(s) quarantined for conflicting content (V10)")
    if rows == 0:
        warnings.append("no usable rows: nothing to analyse (see the rejects report)")
    reject_rate = rejects / source_rows if source_rows else 0.0
    if reject_rate > 0.20:
        warnings.append("more than 20% of rows were rejected; check the mapping profile before running")

    return CapabilityProfile(
        rows=rows,
        txs=txs,
        addresses=addresses,
        ips=ips,
        span_from_us=span[0],
        span_to_us=span[1],
        amount_unit=amount_unit,
        network=NetworkCapability(
            present=has_network,
            observation_model=model,
            distinct_src_ips=distinct_src,
            distinct_dst_ips=distinct_dst,
            dst_8333_share=round(dst_8333, 4),
            obs_per_tx_p50=round(p50, 2),
            obs_per_tx_p90=round(p90, 2),
            sensors_inferred=sensors,
        ),
        fields={
            "fee": "provided" if fee_provided >= 0.5 else "computed",
            "script_type": "inferred from address form",
            "prevouts": "absent",
        },
        quality={
            "source_rows": source_rows,
            "rejects": rejects,
            "reject_rate": round(reject_rate, 6),
            "duplicates": duplicates,
            "conflict_txids": conflicts,
        },
        enabled_stages=stages,
        disabled_features=disabled,
        warnings=warnings,
    )
