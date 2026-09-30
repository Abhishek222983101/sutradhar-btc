"""Train the change-address model on generated worlds (labels: is_change from ground truth)."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import duckdb
import polars as pl
from sklearn.linear_model import LogisticRegression

from sutradhar_engine.change_model import FEATURE_SQL, FEATURES
from sutradhar_engine.linear_model import MODELS_DIR
from sutradhar_evals.metrics import build_world
from sutradhar_gen.config import PRESETS

TRAIN_SEEDS = tuple(range(200, 216))


def world_rows(seed: int, tmp: Path, scenario: str) -> pl.DataFrame:
    world = build_world(PRESETS[scenario], seed, tmp / f"w{seed}")
    con = duckdb.connect()
    con.execute(f"ATTACH '{(world.dataset_dir / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    con.execute(f"ATTACH '{(world.run_dir / 'run.duckdb').as_posix()}' AS run (READ_ONLY)")
    con.execute("CREATE TEMP TABLE coinjoin AS SELECT * FROM run.coinjoin")
    con.execute(FEATURE_SQL)
    feats = pl.from_arrow(con.execute("SELECT * FROM change_feat WHERE frac_of_input IS NOT NULL").arrow())
    con.close()
    truth = pl.read_parquet(world.world_dir / "truth" / "outputs.parquet").select(
        "txid", pl.col("vout").alias("idx"), pl.col("is_change").cast(pl.Int8).alias("y")
    )
    shutil.rmtree(world.world_dir.parent, ignore_errors=True)
    return feats.join(truth, on=["txid", "idx"])


def main(seeds: tuple[int, ...] = TRAIN_SEEDS) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        frames = [world_rows(s, Path(tmp), "rich" if s % 2 else "demo") for s in seeds]
    data = pl.concat(frames)
    x = data.select(FEATURES).to_numpy().astype(float)
    y = data["y"].to_numpy()
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit((x - mean) / scale, y)
    payload = {
        "version": "change-lr@1",
        "features": list(FEATURES),
        "weights": [float(w) for w in model.coef_[0]],
        "bias": float(model.intercept_[0]),
        "mean": [float(m) for m in mean],
        "scale": [float(s) for s in scale],
        "trained_on": {"seeds": list(seeds), "rows": len(y), "positives": int(y.sum())},
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    (MODELS_DIR / "change_lr.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(main()["trained_on"]))
