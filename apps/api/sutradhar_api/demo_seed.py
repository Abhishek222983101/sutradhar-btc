"""Demo boot: load the bundled synthetic "hero" world so the very first request already has results.

The world is generated data (RFC 5737 IPs, invented addresses). Measured accuracy against its hidden ground
truth is stored alongside, so the UI can show honest numbers instead of claims.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.config import Settings
from sutradhar_api.db import Database, utcnow
from sutradhar_api.jobs.handlers import HANDLERS
from sutradhar_api.jobs.queue import Claim
from sutradhar_api.models import Dataset, DatasetFile, Job, Run
from sutradhar_api.routes.runs import MODEL_VERSIONS
from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_engine.settings import EngineSettings
from sutradhar_schemas.canonical import sha256_file

log = logging.getLogger("sutradhar.demo")
HERO = Path(__file__).parent / "demo" / "hero_traffic.csv"
HERO_DATASET, HERO_RUN = "ds_hero", "run_hero"
EVAL_JSON = Path(__file__).parent / "demo" / "eval.json"


def seed_hero(db: Database, settings: Settings) -> None:
    with db.read() as session:
        if session.get(Dataset, HERO_DATASET) is not None:
            return
    data = settings.data_dir
    for folder in ("uploads", "datasets", "runs"):
        shutil.rmtree(data / folder / (HERO_DATASET if folder != "runs" else HERO_RUN), ignore_errors=True)
    (data / "uploads" / HERO_DATASET).mkdir(parents=True, exist_ok=True)
    shutil.copy(HERO, data / "uploads" / HERO_DATASET / "traffic.csv")
    ingested = ingest(
        [data / "uploads" / HERO_DATASET / "traffic.csv"],
        CANONICAL_CSV,
        data / "datasets" / HERO_DATASET,
        HERO_DATASET,
    )
    shutil.copy(HERO.with_name("hero_watchlist.csv"), data / "datasets" / HERO_DATASET / "watchlist.csv")
    manifest = run_pipeline(
        data / "datasets" / HERO_DATASET,
        data / "runs" / HERO_RUN,
        HERO_RUN,
        settings=EngineSettings(threads=settings.engine_threads),
    )
    now = utcnow()
    with db.write() as s:
        s.add(
            Dataset(
                id=HERO_DATASET,
                name="Hero world (synthetic)",
                status="uploaded",
                source="generator",
                bytes=HERO.stat().st_size,
                created_by=None,
                created_at=now,
            )
        )
        s.flush()
        s.add(
            DatasetFile(
                id="file_hero",
                dataset_id=HERO_DATASET,
                filename="traffic.csv",
                format="csv",
                sha256=sha256_file(HERO),
                bytes=HERO.stat().st_size,
                created_at=now,
            )
        )
        s.add(
            Run(
                id=HERO_RUN,
                dataset_id=HERO_DATASET,
                status="running",
                config=EngineSettings(threads=settings.engine_threads).model_dump(mode="json"),
                model_versions=MODEL_VERSIONS,
                refdata_versions={},
                created_by=None,
                created_at=now,
            )
        )
        for job_id, kind, payload in (
            ("job_hero_ingest", "ingest", {"dataset_id": HERO_DATASET}),
            ("job_hero_run", "run", {"run_id": HERO_RUN, "dataset_id": HERO_DATASET}),
        ):
            s.add(
                Job(
                    id=job_id,
                    kind=kind,
                    payload=payload,
                    status="succeeded",
                    attempts=1,
                    max_attempts=1,
                    cancel_requested=False,
                    created_at=now,
                    finished_at=now,
                )
            )
        s.flush()
        HANDLERS["ingest"].on_success(
            s,
            Claim("job_hero_ingest", "ingest", {"dataset_id": HERO_DATASET}, 1, "seed"),
            {
                "manifest": ingested.manifest.model_dump(mode="json"),
                "capability": ingested.capability.model_dump(mode="json"),
            },
            data,
        )
        HANDLERS["run"].on_success(
            s,
            Claim("job_hero_run", "run", {"run_id": HERO_RUN, "dataset_id": HERO_DATASET}, 1, "seed"),
            {"manifest": manifest.model_dump(mode="json")},
            data,
        )
        s.commit()
    log.info("hero world loaded: %s", HERO_RUN)


def hero_leads_exist(db: Database) -> bool:
    with db.read() as session:
        return session.scalar(select(Run.id).where(Run.id == HERO_RUN)) is not None


__all__ = ["EVAL_JSON", "audit", "seed_hero"]
