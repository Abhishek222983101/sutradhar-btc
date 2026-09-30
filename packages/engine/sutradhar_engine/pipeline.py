"""Run orchestration: open a fresh run store, attach the dataset read-only, run the stages, freeze the run."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import duckdb
import numpy as np

from sutradhar_engine.plugins import load_plugin_stages
from sutradhar_engine.runner import Progress, RunContext, Stage, _noop, run_stages
from sutradhar_engine.settings import EngineSettings
from sutradhar_engine.stages import (
    e01_load,
    e02_enrich,
    e03_flows,
    e04_coinjoin,
    e05_cluster,
    e06_change,
    e07_peel,
    e08_anomaly,
    e09_origin,
    e11_coorigin,
    e12_embed,
    e13_taint,
    e14_fingerprint,
    e15_motifs,
    e16_suggest,
    e17_rank,
    e18_explain,
    e19_publish,
    e20_services,
    e21_risk,
    e22_actor_features,
)
from sutradhar_engine.store.ddl import RUN_BASE_DDL
from sutradhar_schemas.evidence import CapabilityProfile, RunManifest
from sutradhar_schemas.ids import check_id

DEFAULT_STAGES: tuple[Stage, ...] = (
    e01_load.STAGE,
    e02_enrich.STAGE,
    e04_coinjoin.STAGE,
    e06_change.STAGE,
    e05_cluster.STAGE,
    e03_flows.STAGE,
    e12_embed.STAGE,
    e15_motifs.STAGE,
    e07_peel.STAGE,
    e08_anomaly.STAGE,
    e09_origin.STAGE,
    e11_coorigin.STAGE,
    e20_services.STAGE,
    e13_taint.STAGE,
    e21_risk.STAGE,
    e22_actor_features.STAGE,
    e14_fingerprint.STAGE,
    e16_suggest.STAGE,
    e17_rank.STAGE,
    e18_explain.STAGE,
    e19_publish.STAGE,
)


def with_plugins(stages: Sequence[Stage]) -> tuple[Stage, ...]:
    """Core stages with plugin stages inserted just before lead ranking (E17)."""
    extra = load_plugin_stages()
    core = list(stages)
    at = next((i for i, st in enumerate(core) if st.code == "E17"), len(core))
    return (*core[:at], *extra, *core[at:])


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def run_pipeline(
    dataset_dir: Path,
    run_dir: Path,
    run_id: str,
    *,
    settings: EngineSettings | None = None,
    progress: Progress = _noop,
    stages: Sequence[Stage] | None = None,
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
        run_stages(ctx, with_plugins(DEFAULT_STAGES) if stages is None else stages)
        con.execute("DETACH ds")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    run_db.chmod(0o444)  # a completed run is immutable (I3)
    return RunManifest.model_validate(ctx.meta["manifest"])
