"""Metrics computed against ground truth. Only this package may read `truth/*.parquet` (I7)."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import polars as pl

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_engine.settings import EngineSettings
from sutradhar_gen.config import ScenarioConfig
from sutradhar_gen.generate import generate


@dataclass(frozen=True)
class WorldRun:
    world_dir: Path
    dataset_dir: Path
    run_dir: Path
    run_id: str


def build_world(
    cfg: ScenarioConfig, seed: int, out: Path, *, settings: EngineSettings | None = None
) -> WorldRun:
    """Generate a world, ingest it, and run the engine over it. `out` is wiped first (reproducible)."""
    shutil.rmtree(out, ignore_errors=True)
    generate(cfg, seed, out / "world")
    files = [out / "world" / "data" / "traffic.csv"]
    ingest(files, CANONICAL_CSV, out / "ds", f"ds_eval_{seed}")
    watchlist = out / "world" / "data" / "watchlist.csv"
    if watchlist.exists():
        shutil.copy(watchlist, out / "ds" / "watchlist.csv")
    run_id = f"run_eval_{seed}"
    run_pipeline(out / "ds", out / "run", run_id, settings=settings or EngineSettings())
    return WorldRun(out / "world", out / "ds", out / "run", run_id)


@dataclass(frozen=True)
class OriginMetrics:
    observable_transactions: int
    total_transactions: int
    top1_accuracy: float
    top3_accuracy: float
    random_baseline: float


def origin_accuracy(world: WorldRun) -> OriginMetrics:
    truth = pl.read_parquet(world.world_dir / "truth" / "origins.parquet").filter(pl.col("observable"))
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    con.execute(f"ATTACH '{(world.dataset_dir / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    top1 = pl.from_arrow(con.execute("SELECT txid, ip FROM origin WHERE rnk = 1").arrow())
    top3 = pl.from_arrow(con.execute("SELECT txid, ip FROM origin WHERE rnk <= 3").arrow())
    total_tx = con.execute("SELECT count(*) FROM d_tx").fetchone()
    total = int(total_tx[0]) if total_tx else 0
    # True candidate pool per tx: every distinct IP that announced it at all, not just the top-k kept in `origin`.
    pool = con.execute(
        "SELECT avg(1.0 / n) FROM (SELECT count(DISTINCT src_ip) n FROM ds.obs WHERE src_ip IS NOT NULL GROUP BY txid)"
    ).fetchone()
    con.close()
    j1 = truth.join(top1, on="txid")
    j3 = truth.join(top3, on="txid")
    t1 = float((j1["origin_ip"] == j1["ip"]).mean()) if j1.height else 0.0
    t3 = (
        float(j3.group_by("txid").agg((pl.col("origin_ip") == pl.col("ip")).any().alias("h"))["h"].mean())
        if j3.height
        else 0.0
    )
    baseline = round(float(pool[0]), 4) if pool and pool[0] else 0.0
    return OriginMetrics(truth.height, total, round(t1, 4), round(t3, 4), round(baseline, 4))


@dataclass(frozen=True)
class ClusterMetrics:
    clusters: int
    pure_clusters: int
    purity: float
    addresses_in_impure: int


def cluster_purity(world: WorldRun) -> ClusterMetrics:
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet").select("address", "agent_id")
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    cl = pl.from_arrow(con.execute("SELECT address, cluster_id FROM cluster").arrow())
    con.close()
    joined = cl.join(addr, on="address")
    per_cluster = joined.group_by("cluster_id").agg(
        pl.col("agent_id").n_unique().alias("k"), pl.len().alias("n")
    )
    pure = int((per_cluster["k"] == 1).sum())
    total = per_cluster.height
    return ClusterMetrics(
        clusters=total,
        pure_clusters=pure,
        purity=round(pure / total, 4) if total else 0.0,
        addresses_in_impure=int(per_cluster.filter(pl.col("k") > 1)["n"].sum()),
    )


@dataclass(frozen=True)
class CoinJoinMetrics:
    truth_coinjoins: int
    flagged: int
    precision: float
    recall: float


def coinjoin_detection(world: WorldRun, min_p: float = 0.5) -> CoinJoinMetrics:
    truth = pl.read_parquet(world.world_dir / "truth" / "txs.parquet").filter(pl.col("exported"))
    actual = set(truth.filter(pl.col("kind") == "coinjoin")["txid"].to_list())
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    flagged = {r[0] for r in con.execute("SELECT txid FROM coinjoin WHERE p >= ?", [min_p]).fetchall()}
    con.close()
    tp = len(actual & flagged)
    return CoinJoinMetrics(
        len(actual),
        len(flagged),
        round(tp / len(flagged), 4) if flagged else 1.0,
        round(tp / len(actual), 4) if actual else 1.0,
    )


def purity_without_guard(world: WorldRun) -> float:
    """Ablation: cluster purity if CoinJoin inputs WERE merged (what the I8 guard prevents)."""
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet").select("address", "agent_id")
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    con.execute(f"ATTACH '{(world.dataset_dir / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    rows = con.execute("SELECT list(address) FROM ds.txin GROUP BY txid").fetchall()
    con.close()
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (addrs,) in rows:
        for a in addrs[1:]:
            parent[find(a)] = find(addrs[0])
        find(addrs[0])
    owner = dict(zip(addr["address"].to_list(), addr["agent_id"].to_list(), strict=True))
    members: dict[str, set[str]] = {}
    for a in parent:
        members.setdefault(find(a), set()).add(owner.get(a, a))
    pure = sum(1 for v in members.values() if len(v) == 1)
    return round(pure / len(members), 4) if members else 0.0


@dataclass(frozen=True)
class EvalReport:
    scenario: str
    seed: int
    origin: OriginMetrics
    cluster: ClusterMetrics
    coinjoin: CoinJoinMetrics
    purity_if_coinjoins_merged: float

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "seed": self.seed,
            "origin": asdict(self.origin),
            "cluster": asdict(self.cluster),
            "coinjoin": asdict(self.coinjoin),
            "purity_if_coinjoins_merged": self.purity_if_coinjoins_merged,
        }


def evaluate(cfg: ScenarioConfig, seed: int, out: Path) -> EvalReport:
    world = build_world(cfg, seed, out)
    return EvalReport(
        cfg.name,
        seed,
        origin_accuracy(world),
        cluster_purity(world),
        coinjoin_detection(world),
        purity_without_guard(world),
    )
