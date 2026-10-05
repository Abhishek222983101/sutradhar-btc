"""Train the CoinJoin classifier on generated worlds (labels: kind == "coinjoin" from ground truth).

Training worlds (seeds 400-459) are domain-randomised: coordinator denomination, participant counts, round cadence and
the benign look-alike mix (merchants, payroll, traders, mining pools, gambling) all vary, so the model learns what makes
a mix a mix rather than one configuration. Validation worlds (460-471) are held out by world, never by row, and report
precision/recall against the scored heuristic the model replaced. Evaluation seeds (1-5) and the stress seeds in
`tests/` are never used here. Output is plain JSON weights the engine loads without importing this package (I7).
Run: `uv run sutradhar evals train-coinjoin`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression

from sutradhar_engine.coinjoin_model import FEATURE_SQL, FEATURES, MIN_INPUTS, MIN_OUTPUTS, RULE_SQL
from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.linear_model import MODELS_DIR
from sutradhar_gen.config import PRESETS, CoinJoinCfg, LookalikeCfg, OpsCfg, ScenarioConfig
from sutradhar_gen.generate import generate

TRAIN_SEEDS = tuple(range(400, 460))
VALID_SEEDS = tuple(range(460, 472))
THRESHOLD = 0.5


def scenario_for(seed: int) -> ScenarioConfig:
    """A randomised mixing scenario for `seed`: varied coordinators, varied benign look-alikes."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 7]))
    base = PRESETS["hard" if seed % 2 else "rich"]
    n_coord = int(rng.integers(1, 3))
    coordinators = tuple(
        CoinJoinCfg(
            op_id=f"mix{i}",
            rounds=int(rng.integers(6, 16)),
            participants_min=(lo := int(rng.integers(3, 8))),
            participants_max=lo + int(rng.integers(0, 6)),
            denomination_btc=float(rng.choice([0.01, 0.02, 0.05, 0.1, 0.2])),
            first_round_day=float(rng.uniform(0.6, 1.5)),
            interval_h=float(rng.uniform(5.0, 14.0)),
        )
        for i in range(n_coord)
    )
    lookalikes = LookalikeCfg(
        merchants=int(rng.integers(1, 6)),
        payroll_employers=int(rng.integers(1, 3)),
        payroll_employees=int(rng.integers(4, 16)),
        traders=int(rng.integers(1, 6)),
        pools=int(rng.integers(1, 4)),
        pool_miners=int(rng.integers(4, 20)),
        pool_block_every_h=float(rng.uniform(0.5, 2.0)),
        pool_payout_every_h=float(rng.uniform(4.0, 12.0)),
        gambling_sites=int(rng.integers(0, 2)),
    )
    return base.model_copy(
        update={"ops": OpsCfg(coinjoin=coordinators, darknet=base.ops.darknet), "lookalikes": lookalikes}
    )


def world_rows(seed: int, tmp: Path, cfg: ScenarioConfig | None = None) -> pl.DataFrame:
    """Candidate features plus the ground-truth label and the heuristic baseline's score, for one world."""
    world = tmp / f"w{seed}"
    generate(cfg or scenario_for(seed), seed, world)
    ingest([world / "data" / "traffic.csv"], CANONICAL_CSV, world / "ds", f"ds_cj_{seed}")
    con = duckdb.connect()
    con.execute(f"ATTACH '{(world / 'ds' / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)")
    con.execute(FEATURE_SQL.format(min_in=MIN_INPUTS, min_out=MIN_OUTPUTS))
    feats = pl.from_arrow(con.execute("SELECT * FROM coinjoin_feat").arrow())
    con.execute(RULE_SQL)
    rule = pl.from_arrow(con.execute("SELECT txid, p AS rule_p FROM coinjoin").arrow())
    con.close()
    txs = pl.read_parquet(world / "truth" / "txs.parquet").filter(pl.col("exported"))
    truth = txs.select("txid", (pl.col("kind") == "coinjoin").cast(pl.Int8).alias("y"))
    shutil.rmtree(world, ignore_errors=True)
    out = feats.join(truth, on="txid").join(rule, on="txid", how="left")
    return out.with_columns(pl.col("rule_p").fill_null(0.0), pl.lit(seed).alias("seed"))


def _prf(y: np.ndarray, flagged: np.ndarray, n_truth: int) -> dict[str, float]:
    tp = int((y[flagged] == 1).sum())
    precision = tp / int(flagged.sum()) if flagged.any() else 1.0
    recall = tp / n_truth if n_truth else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def main(
    seeds: tuple[int, ...] = TRAIN_SEEDS, valid_seeds: tuple[int, ...] = VALID_SEEDS, out: Path | None = None
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        train = pl.concat([world_rows(s, Path(tmp)) for s in seeds])
        valid = pl.concat([world_rows(s, Path(tmp)) for s in valid_seeds])
    x = train.select(FEATURES).to_numpy().astype(float)
    y = train["y"].to_numpy()
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=5.0, max_iter=5000).fit((x - mean) / scale, y)
    xv = valid.select(FEATURES).to_numpy().astype(float)
    pv = model.predict_proba((xv - mean) / scale)[:, 1]
    yv = valid["y"].to_numpy()
    n_truth = int(yv.sum())
    model_scores = _prf(yv, pv >= THRESHOLD, n_truth)
    rule_scores = _prf(yv, valid["rule_p"].to_numpy() >= THRESHOLD, n_truth)
    payload = {
        "version": "coinjoin-lr@1",
        "features": list(FEATURES),
        "weights": [float(w) for w in model.coef_[0]],
        "bias": float(model.intercept_[0]),
        "mean": [float(m) for m in mean],
        "scale": [float(s) for s in scale],
        "trained_on": {
            "seeds": list(seeds),
            "validation_seeds": list(valid_seeds),
            "rows": len(y),
            "positives": int(y.sum()),
            "validation_rows": len(yv),
            "validation_positives": n_truth,
            "validation_precision": model_scores["precision"],
            "validation_recall": model_scores["recall"],
            "validation_f1": model_scores["f1"],
            "baseline_rule_precision": rule_scores["precision"],
            "baseline_rule_recall": rule_scores["recall"],
            "baseline_rule_f1": rule_scores["f1"],
        },
    }
    target = out or MODELS_DIR / "coinjoin_lr.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    info = main()["trained_on"]
    print(json.dumps({k: v for k, v in info.items() if k.startswith(("validation_", "baseline_"))}))
