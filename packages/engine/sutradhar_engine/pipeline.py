"""Run orchestration: open a fresh run store, attach the dataset read-only, run the stages, freeze the run."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import duckdb
import numpy as np

from sutradhar_engine.runner import Progress, RunContext, Stage, _noop, run_stages
from sutradhar_engine.settings import EngineSettings
from sutradhar_engine.stages import (
    e01_load,
    e02_enrich,
    e04_coinjoin,
    e05_cluster,
    e07_peel,
    e08_anomaly,
    e09_origin,
    e13_taint,
    e17_rank,
    e19_publish,
)
from sutradhar_engine.store.ddl import RUN_BASE_DDL
from sutradhar_schemas.evidence import CapabilityProfile, RunManifest
from sutradhar_schemas.ids import check_id

DEFAULT_STAGES: tuple[Stage, ...] = (
    e01_load.STAGE,
    e02_enrich.STAGE,
    e04_coinjoin.STAGE,
    e05_cluster.STAGE,
    e07_peel.STAGE,
    e08_anomaly.STAGE,
    e09_origin.STAGE,
    e13_taint.STAGE,
    e17_rank.STAGE,
    e19_publish.STAGE,
)


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def run_pipeline(
    dataset_dir: Path,
    run_dir: Path,
    run_id: str,
    *,
    settings: EngineSettings | None = None,
    progress: Progress = _noop,
    stages: Sequence[Stage] = DEFAULT_STAGES,
) -> RunManifest:
    check_id(run_id, "run")
    settings = settings or EngineSettings()
    dataset_db = dataset_dir / "dataset.duckdb"
    if not dataset_db.exists():
        raise FileNotFoundError(f"no dataset store at {dataset_db}")
    run_dir.mkdir(parents=True, exist_ok=True)
    run_db = run_dir / "run.duckdb"
    if run_db.exists():
        raise FileExistsError(f"{run_db} already exists; runs are immutable")
    dataset_manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    capability = CapabilityProfile.model_validate_json(
        (dataset_dir / "xray.json").read_text(encoding="utf-8")
    )

    con = duckdb.connect(str(run_db))
    try:
        con.execute(f"SET threads TO {int(settings.threads)}")
        con.execute(RUN_BASE_DDL)
        con.execute(f"ATTACH '{_sql_path(dataset_db)}' AS ds (READ_ONLY)")
        ctx = RunContext(
            run_id=run_id,
            run_dir=run_dir,
            con=con,
            dataset_path=dataset_db,
            dataset_manifest=dataset_manifest,
            capability=capability,
            settings=settings,
            rng=np.random.default_rng(settings.seed),
            progress=progress,
        )
        run_stages(ctx, stages)
        con.execute("DETACH ds")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    run_db.chmod(0o444)  # a completed run is immutable (I3)
    return RunManifest.model_validate(ctx.meta["manifest"])
