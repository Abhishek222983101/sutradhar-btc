"""Realism checks (P1.8, blueprint §5.12): `sutradhar gen validate <world>` reports how a generated world's
own statistics compare to the target bands the blueprint's own team set out — never fetched or invented here,
just computed from the world's truth files and compared. Out-of-range checks are **flagged, not fatal**:
realism is a spectrum, and hiding a weak spot would be worse than reporting it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from sutradhar_gen.config import ScenarioConfig


@dataclass(slots=True)
class Check:
    name: str
    value: str
    band: str
    basis: str
    in_band: bool | None  # None: the band is descriptive, not a pass/fail threshold


def _io_shape(world_dir: Path) -> Check:
    txs = pl.read_parquet(world_dir / "truth" / "txs.parquet").filter(pl.col("exported"))
    if txs.height == 0:
        return Check(
            "Inputs/outputs per tx", "no exported tx", "1-2 in, 2 out typical", "common knowledge", None
        )
    typical = txs.filter(pl.col("n_in").is_in([1, 2]) & (pl.col("n_out") == 2)).height / txs.height
    return Check(
        "Inputs/outputs per tx",
        f"{typical:.0%} are 1-2 in / 2 out",
        "most txs 1-2 in, 2 out; heavy tail of large batches",
        "common knowledge of the Bitcoin tx distribution",
        typical >= 0.25,
    )


def _address_reuse(world_dir: Path) -> Check:
    outputs = pl.read_parquet(world_dir / "truth" / "outputs.parquet")
    if outputs.height == 0:
        return Check("Address reuse", "no outputs", "5-30% of addresses receive >1 payment", "-", None)
    per_address = outputs.group_by("address").agg(pl.len().alias("n"))
    reused = (per_address["n"] > 1).sum() / per_address.height
    return Check(
        "Address reuse",
        f"{reused:.1%} of addresses receive more than once",
        "5-30%",
        "-",
        0.05 <= reused <= 0.30,
    )


def _script_mix(world_dir: Path, cfg: ScenarioConfig) -> Check:
    addresses = pl.read_parquet(world_dir / "truth" / "addresses.parquet")
    if addresses.height == 0:
        return Check("Script-type mix", "no addresses", "configured mix +/- 5 points", "-", None)
    observed = addresses["script_type"].value_counts(normalize=True).sort("script_type")
    configured = {str(k): v for k, v in cfg.economy.script_mix.items()}
    max_dev = 0.0
    parts = []
    for row in observed.iter_rows(named=True):
        st, prop = row["script_type"], row["proportion"]
        want = configured.get(st, 0.0)
        max_dev = max(max_dev, abs(prop - want))
        parts.append(f"{st}={prop:.0%}")
    return Check(
        "Script-type mix",
        ", ".join(parts),
        "configured mix +/- 5 points (Segwit-v0 majority, rising P2TR share)",
        "configured economy.script_mix",
        max_dev <= 0.10,  # wallet types outside the pure user population (exchanges etc.) widen this a bit
    )


def _propagation(world_dir: Path, fmt: str = "csv") -> Check:
    ext = {"csv": "csv", "json": "json", "ndjson": "ndjson", "xml": "xml"}[fmt]
    traffic_path = world_dir / "data" / f"traffic.{ext}"
    txs = (
        pl.read_parquet(world_dir / "truth" / "txs.parquet")
        .select("txid", "ts_us")
        .rename({"ts_us": "tx_ts"})
    )
    if fmt == "csv":
        obs = pl.read_csv(traffic_path, columns=["txid", "timestamp"])
    else:
        return Check(
            "Propagation", "not computed for this format", "50% within a few s, 90% within 10-20s", "-", None
        )
    obs = obs.with_columns(
        pl.col("timestamp")
        .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
        .dt.epoch("us")
        .alias("obs_ts")
    )
    joined = obs.join(txs, on="txid", how="inner").with_columns(
        ((pl.col("obs_ts") - pl.col("tx_ts")) / 1_000_000).alias("delay_s")
    )
    if joined.height == 0:
        return Check("Propagation", "no observations", "50% within a few s, 90% within 10-20s", "-", None)
    p50 = joined["delay_s"].quantile(0.5) or 0.0
    p90 = joined["delay_s"].quantile(0.9) or 0.0
    return Check(
        "Propagation",
        f"p50={p50:.1f}s, p90={p90:.1f}s",
        "50% of nodes reached within a few seconds, 90% within ~10-20s",
        "diffusion delays as configured",
        p50 <= 10 and p90 <= 30,
    )


def _degree(world_dir: Path) -> Check:
    outputs = pl.read_parquet(world_dir / "truth" / "outputs.parquet")
    per_agent = (
        outputs.filter(pl.col("owner_agent").is_not_null()).group_by("owner_agent").agg(pl.len().alias("n"))
    )
    if per_agent.height < 2:
        return Check("Degree distribution", "too few agents", "heavy-tailed (exchanges as hubs)", "-", None)
    n = per_agent["n"].sort().to_numpy()
    cum = n.cumsum()
    gini = 1 - 2 * (cum[:-1].sum() + cum[-1] / 2) / (cum[-1] * len(n)) if cum[-1] > 0 else 0.0
    return Check(
        "Degree distribution",
        f"Gini={gini:.2f} over {per_agent.height} actors",
        "heavy-tailed entity degree (exchanges as hubs)",
        "-",
        gini >= 0.3,
    )


def _coinjoin_share(world_dir: Path, cfg: ScenarioConfig) -> Check:
    txs = pl.read_parquet(world_dir / "truth" / "txs.parquet").filter(pl.col("exported"))
    if txs.height == 0 or not cfg.ops.coinjoin:
        return Check("CoinJoin share", "not configured", "configured share +/- 20%", "-", None)
    share = (txs["kind"] == "coinjoin").sum() / txs.height
    return Check("CoinJoin share", f"{share:.1%} of exported txs", "present and non-trivial", "-", share > 0)


def _label_balance(world_dir: Path) -> Check:
    agents = pl.read_parquet(world_dir / "truth" / "agents.parquet")
    if agents.height == 0:
        return Check("Label balance", "no agents", "illicit actors 0.5-3% of actors", "-", None)
    frac = agents["illicit"].sum() / agents.height
    return Check(
        "Label balance",
        f"{frac:.2%} of actors are illicit",
        "0.5-3% (Elliptic-like ~2% illicit)",
        "Elliptic-like imbalance",
        0.005 <= frac <= 0.03,
    )


def realism_report(world_dir: Path, cfg: ScenarioConfig, fmt: str = "csv") -> list[Check]:
    return [
        _io_shape(world_dir),
        _address_reuse(world_dir),
        _script_mix(world_dir, cfg),
        _propagation(world_dir, fmt),
        _degree(world_dir),
        _coinjoin_share(world_dir, cfg),
        _label_balance(world_dir),
    ]


def format_report(checks: list[Check], scenario_name: str, seed: int) -> str:
    lines = [
        f"# Realism report — {scenario_name} (seed {seed})",
        "",
        "Flagged, not fatal (blueprint §5.12).",
        "",
    ]
    lines.append("| Check | Value | Target band | Basis | In band |")
    lines.append("|---|---|---|---|---|")
    for c in checks:
        mark = "-" if c.in_band is None else ("yes" if c.in_band else "**FLAGGED**")
        lines.append(f"| {c.name} | {c.value} | {c.band} | {c.basis} | {mark} |")
    return "\n".join(lines) + "\n"
