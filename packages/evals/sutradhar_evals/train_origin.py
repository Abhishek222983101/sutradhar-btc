"""Train the origin model (logistic regression over per-candidate timing features) on generated worlds.

Training seeds (100-119) never overlap the evaluation seeds (1-5). Output is plain JSON weights, which the engine
loads without importing this package (I7). Run: `uv run sutradhar evals train-origin`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import duckdb
import polars as pl
from sklearn.linear_model import LogisticRegression

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.origin_model import FEATURE_SQL, FEATURES, MODEL_PATH
from sutradhar_gen.config import PRESETS
from sutradhar_gen.generate import generate

TRAIN_SEEDS = tuple(range(100, 120))


def _world_rows(seed: int, tmp: Path) -> pl.DataFrame:
    world = tmp / f"w{seed}"
    generate(PRESETS["demo"], seed, world)
    ingest([world / "data" / "traffic.csv"], CANONICAL_CSV, world / "ds", f"ds_train_{seed}")
    con = duckdb.connect()
    con.execute(f"ATTACH '{(world / 'ds' / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    con.execute(FEATURE_SQL)
    feats = pl.from_arrow(con.execute("SELECT * FROM origin_feat").arrow())
    con.close()
    truth = pl.read_parquet(world / "truth" / "origins.parquet").select("txid", "origin_ip")
    shutil.rmtree(world, ignore_errors=True)
    return feats.join(truth, on="txid").with_columns(
        (pl.col("ip") == pl.col("origin_ip")).cast(pl.Int8).alias("y")
    )


def main(seeds: tuple[int, ...] = TRAIN_SEEDS, out: Path = MODEL_PATH) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        frames = [_world_rows(seed, Path(tmp)) for seed in seeds]
    data = pl.concat(frames)
    x = data.select(FEATURES).to_numpy().astype(float)
    y = data["y"].to_numpy()
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced").fit((x - mean) / scale, y)
    payload = {
        "version": "origin-lr@1",
        "features": list(FEATURES),
        "weights": [float(w) for w in model.coef_[0]],
        "bias": float(model.intercept_[0]),
        "mean": [float(m) for m in mean],
        "scale": [float(s) for s in scale],
        "trained_on": {
            "scenario": "demo",
            "seeds": list(seeds),
            "rows": len(y),
            "positives": int(y.sum()),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(main()["trained_on"]))
