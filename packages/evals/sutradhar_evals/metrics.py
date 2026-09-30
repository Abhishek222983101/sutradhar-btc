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
    first_spy_top1: float
    ceiling: float  # share of observable transactions whose true origin announced at all


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
    spy = pl.from_arrow(
        con.execute(
            "SELECT txid, arg_min(src_ip, ts_us) AS ip FROM ds.obs WHERE src_ip IS NOT NULL GROUP BY txid"
        ).arrow()
    )
    announced = pl.from_arrow(
        con.execute("SELECT DISTINCT txid, src_ip AS ip FROM ds.obs WHERE src_ip IS NOT NULL").arrow()
    )
    con.close()
    heard = (
        truth.join(announced, on="txid")
        .group_by("txid")
        .agg((pl.col("origin_ip") == pl.col("ip")).any().alias("h"))
    )
    ceiling = round(float(heard["h"].sum()) / truth.height, 4) if truth.height else 0.0
    js = truth.join(spy, on="txid")
    first_spy = round(float((js["origin_ip"] == js["ip"]).mean()), 4) if js.height else 0.0
    j1 = truth.join(top1, on="txid")
    j3 = truth.join(top3, on="txid")
    t1 = float((j1["origin_ip"] == j1["ip"]).mean()) if j1.height else 0.0
    t3 = (
        float(j3.group_by("txid").agg((pl.col("origin_ip") == pl.col("ip")).any().alias("h"))["h"].mean())
        if j3.height
        else 0.0
    )
    baseline = round(float(pool[0]), 4) if pool and pool[0] else 0.0
    return OriginMetrics(
        truth.height, total, round(t1, 4), round(t3, 4), round(baseline, 4), first_spy, ceiling
    )


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
class ChangeMetrics:
    scored_outputs: int
    argmax_accuracy: float  # per transaction, is the highest-scoring output the true change?
    merge_links: int  # outputs at or above the merge threshold
    merge_precision: float  # of those, how many are truly change


def change_detection(world: WorldRun, merge_p: float | None = None) -> ChangeMetrics:
    merge_p = EngineSettings().change_merge_min_p if merge_p is None else merge_p
    truth = pl.read_parquet(world.world_dir / "truth" / "outputs.parquet").select(
        "txid", pl.col("vout").alias("idx"), "is_change"
    )
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    scored = pl.from_arrow(con.execute("SELECT txid, idx, p FROM change").arrow())
    con.close()
    if not scored.height:
        return ChangeMetrics(0, 0.0, 0, 1.0)
    joined = scored.join(truth, on=["txid", "idx"])
    best = joined.sort("p", descending=True).group_by("txid", maintain_order=True).first()
    has_change = joined.group_by("txid").agg(pl.col("is_change").any().alias("any")).filter(pl.col("any"))
    best = best.join(has_change.select("txid"), on="txid")
    links = joined.filter(pl.col("p") >= merge_p)
    return ChangeMetrics(
        joined.height,
        round(float(best["is_change"].mean()), 4) if best.height else 0.0,
        links.height,
        round(float(links["is_change"].mean()), 4) if links.height else 1.0,
    )


@dataclass(frozen=True)
class PeelMetrics:
    truth_hops: int
    detected_txs: int
    precision: float
    recall: float


def peel_detection(world: WorldRun) -> PeelMetrics:
    truth = pl.read_parquet(world.world_dir / "truth" / "txs.parquet").filter(
        pl.col("exported") & pl.col("peel_chain_id").is_not_null()
    )
    actual = set(truth["txid"].to_list())
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    found = {r[0] for r in con.execute("SELECT txid FROM peel_chain").fetchall()}
    con.close()
    tp = len(actual & found)
    return PeelMetrics(
        len(actual),
        len(found),
        round(tp / len(found), 4) if found else 1.0,
        round(tp / len(actual), 4) if actual else 1.0,
    )


@dataclass(frozen=True)
class SuggestionMetrics:
    suggestions: int
    precision_top50: float
    random_pair_rate: float


def suggestion_quality(world: WorldRun, k: int = 50) -> SuggestionMetrics:
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet").select("address", "agent_id")
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    cl = pl.from_arrow(con.execute("SELECT address, cluster_id FROM cluster").arrow()).join(
        addr, on="address"
    )
    sug = pl.from_arrow(
        con.execute("SELECT a, b FROM merge_suggestion ORDER BY score DESC, a, b LIMIT ?", [k]).arrow()
    )
    total = con.execute("SELECT count(*) FROM merge_suggestion").fetchone()
    con.close()
    owner = (
        cl.group_by("cluster_id", "agent_id")
        .len()
        .sort("len", descending=True)
        .group_by("cluster_id", maintain_order=True)
        .first()
    )
    per_agent = owner.group_by("agent_id").len()["len"].to_list()
    n = owner.height
    pairs = n * (n - 1) / 2
    random_rate = sum(c * (c - 1) / 2 for c in per_agent) / pairs if pairs else 0.0
    m = dict(zip(owner["cluster_id"].to_list(), owner["agent_id"].to_list(), strict=True))
    hits = [
        m.get(a) is not None and m.get(a) == m.get(b)
        for a, b in zip(sug["a"].to_list(), sug["b"].to_list(), strict=True)
    ]
    return SuggestionMetrics(
        int(total[0]) if total else 0, round(sum(hits) / len(hits), 4) if hits else 0.0, round(random_rate, 6)
    )


@dataclass(frozen=True)
class EvalReport:
    scenario: str
    seed: int
    origin: OriginMetrics
    cluster: ClusterMetrics
    coinjoin: CoinJoinMetrics
    purity_if_coinjoins_merged: float
    change: ChangeMetrics
    peel: PeelMetrics
    suggest: SuggestionMetrics

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "seed": self.seed,
            "origin": asdict(self.origin),
            "cluster": asdict(self.cluster),
            "coinjoin": asdict(self.coinjoin),
            "purity_if_coinjoins_merged": self.purity_if_coinjoins_merged,
            "change": asdict(self.change),
            "peel": asdict(self.peel),
            "suggest": asdict(self.suggest),
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
        change_detection(world),
        peel_detection(world),
        suggestion_quality(world),
    )
