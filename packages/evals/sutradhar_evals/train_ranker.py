"""Train the lead ranker: LightGBM on per-actor features, isotonic calibration, clean baseline, drift reference.

Label: the wallet cluster's majority owner is an illicit agent (ransomware operator, darknet market, vendor), taken from
ground truth, which only this package may read. Training worlds (seeds 300-341) never overlap the evaluation worlds
(seeds 1-5). Half of them run with NO watchlist seeds; scenarios cycle through demo, rich and hard (look-alike legitimate actors and slower laundering), so the model cannot just memorise "tainted = illicit".
Run: `uv run sutradhar evals train-ranker`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import polars as pl
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score

from sutradhar_engine.actor_model import FEATURES, MODELS_DIR
from sutradhar_evals.metrics import WorldRun, build_world
from sutradhar_gen.config import PRESETS

TRAIN_SEEDS = tuple(range(300, 342))
SCENARIOS = ("demo", "rich", "hard")
VERSION = "lead-ranker-lgbm@1"


def actor_table(world: WorldRun) -> pl.DataFrame:
    """Features joined with the ground-truth label for one built world."""
    con = duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)
    feats = pl.from_arrow(con.execute("SELECT * FROM actor_features").arrow())
    cl = pl.from_arrow(con.execute("SELECT address, cluster_id FROM cluster").arrow())
    svc = {r[0] for r in con.execute("SELECT cluster_id FROM service").fetchall()}
    con.close()
    agents = pl.read_parquet(world.world_dir / "truth" / "agents.parquet").select("agent_id", "illicit")
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet").select("address", "agent_id")
    owner = (
        cl.join(addr, on="address")
        .join(agents, on="agent_id")
        .group_by("cluster_id")
        .agg((pl.col("illicit").cast(pl.Float64).mean() > 0.5).alias("y"))
    )
    out = feats.join(owner, on="cluster_id", how="left").with_columns(
        pl.col("y").fill_null(False).cast(pl.Int8)
    )
    return out.with_columns(pl.col("cluster_id").is_in(list(svc)).alias("is_service"))


def _world(seed: int, tmp: Path) -> pl.DataFrame:
    scenario = SCENARIOS[seed % 3]
    with_seeds = (seed // 3) % 2 == 0
    world = build_world(PRESETS[scenario], seed, tmp / f"w{seed}", with_seeds=with_seeds)
    table = actor_table(world).with_columns(pl.lit(seed).alias("world"), pl.lit(with_seeds).alias("seeded"))
    shutil.rmtree(tmp / f"w{seed}", ignore_errors=True)
    return table


def collect(seeds: tuple[int, ...] = TRAIN_SEEDS) -> pl.DataFrame:
    with tempfile.TemporaryDirectory() as tmp:
        return pl.concat([_world(s, Path(tmp)) for s in seeds])


def histograms(x: np.ndarray) -> dict[str, dict[str, list[float]]]:
    """Ten-bin reference histograms for the drift check (PSI)."""
    ref: dict[str, dict[str, list[float]]] = {}
    for j, name in enumerate(FEATURES):
        col = x[:, j]
        edges = np.unique(np.quantile(col, np.linspace(0, 1, 11)))
        if len(edges) < 3:
            continue
        counts, _ = np.histogram(col, bins=edges)
        ref[name] = {"edges": [float(e) for e in edges], "frac": [float(c) / len(col) for c in counts]}
    return ref


def train(data: pl.DataFrame, out_dir: Path = MODELS_DIR) -> dict:
    worlds = sorted(data["world"].unique().to_list())
    val_worlds = set(worlds[3::5])  # every fifth world is held out for early stopping and calibration
    tr = data.filter(~pl.col("world").is_in(list(val_worlds)))
    va = data.filter(pl.col("world").is_in(list(val_worlds)))
    xt, yt = tr.select(FEATURES).to_numpy().astype(float), tr["y"].to_numpy()
    xv, yv = va.select(FEATURES).to_numpy().astype(float), va["y"].to_numpy()
    params = {
        "objective": "binary",
        "metric": "average_precision",
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_data_in_leaf": 5,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "lambda_l2": 1.0,
        "scale_pos_weight": float((yt == 0).sum() / max(1, (yt == 1).sum())) ** 0.5,
        "seed": 26146,
        "deterministic": True,
        "force_row_wise": True,
        "num_threads": 1,
        "verbosity": -1,
    }
    booster = lgb.train(
        params,
        lgb.Dataset(xt, yt, feature_name=list(FEATURES)),
        num_boost_round=600,
        valid_sets=[lgb.Dataset(xv, yv, feature_name=list(FEATURES))],
        callbacks=[lgb.early_stopping(40, verbose=False)],
    )
    raw_v = booster.predict(xv, num_threads=1)
    iso = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip").fit(raw_v, yv)
    x_pts = [float(v) for v in iso.X_thresholds_]
    y_pts = [float(v) for v in iso.y_thresholds_]
    negatives = xt[yt == 0]
    meta = {
        "version": VERSION,
        "features": list(FEATURES),
        "baseline": {f: float(np.median(negatives[:, j])) for j, f in enumerate(FEATURES)},
        "calibrator": {"x": x_pts, "y": y_pts},
        "reference_hist": histograms(np.vstack([xt, xv])),
        "trained_on": {
            "seeds": [int(s) for s in worlds],
            "actors": len(data),
            "positives": int(data["y"].sum()),
            "best_iteration": int(booster.best_iteration),
            "validation_pr_auc": float(average_precision_score(yv, raw_v)) if yv.sum() else None,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out_dir / "lead_ranker.txt"))
    (out_dir / "lead_ranker.meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return meta


def main() -> dict:
    return train(collect())


if __name__ == "__main__":
    print(json.dumps(main()["trained_on"]))
