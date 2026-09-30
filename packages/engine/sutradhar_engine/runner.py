"""The run pipeline: a deterministic sequence of stages over one immutable dataset (blueprint §3.4, §6.0).

Each stage declares the tables it REQUIRES and PRODUCES; the runner records timings and row counts,
commits after every stage and can resume a failed run from the last completed stage.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import duckdb
import numpy as np

from sutradhar_engine import __version__
from sutradhar_engine.settings import EngineSettings
from sutradhar_schemas.evidence import CapabilityProfile, StageStat

Progress = Callable[[str, float, str], None]


def _noop(_stage: str, _pct: float, _msg: str) -> None:
    return None


@dataclass
class RunContext:
    run_id: str
    run_dir: Path
    con: duckdb.DuckDBPyConnection
    dataset_path: Path
    dataset_manifest: dict[str, Any]
    capability: CapabilityProfile
    settings: EngineSettings
    rng: np.random.Generator
    progress: Progress = _noop
    stats: dict[str, StageStat] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def put_meta(self, key: str, value: Any) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO run_meta VALUES (?, ?)", [key, json.dumps(value, sort_keys=True)]
        )


@dataclass(frozen=True)
class StageReport:
    rows: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class Stage(Protocol):
    code: str
    name: str
    requires: tuple[str, ...]
    produces: tuple[str, ...]

    def run(self, ctx: RunContext) -> StageReport: ...


class RunError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"{stage}: {message}")
        self.stage = stage


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }


def run_stages(ctx: RunContext, stages: Sequence[Stage], *, resume_after: str | None = None) -> None:
    started = resume_after is None
    for i, stage in enumerate(stages):
        if not started:
            started = stage.code == resume_after
            continue
        if stage.code.startswith("E") and stage.code not in ctx.capability.enabled_stages:
            ctx.stats[stage.code] = StageStat(
                ms=0, notes=["skipped: disabled by the dataset's capability profile"]
            )
            continue
        missing = [t for t in stage.requires if t not in _tables(ctx.con) and not t.startswith("ds.")]
        if missing:
            raise RunError(stage.code, f"missing required tables {missing}")
        ctx.progress(stage.code, i / len(stages), stage.name)
        t0 = time.perf_counter()
        try:
            report = stage.run(ctx)
        except Exception as exc:
            ctx.put_meta("failed_stage", stage.code)
            raise RunError(stage.code, str(exc)) from exc
        produced = [t for t in stage.produces if t not in _tables(ctx.con)]
        if produced:
            raise RunError(stage.code, f"did not produce {produced}")
        ctx.stats[stage.code] = StageStat(
            ms=round((time.perf_counter() - t0) * 1000), rows=report.rows, notes=report.notes
        )
        ctx.put_meta("completed_stage", stage.code)
        ctx.con.execute("CHECKPOINT")
    ctx.progress("done", 1.0, "run complete")


def code_version() -> dict[str, str]:
    return {"engine": __version__}
