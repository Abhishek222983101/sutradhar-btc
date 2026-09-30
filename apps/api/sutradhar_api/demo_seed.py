"""Demo boot: register the pre-built synthetic "hero" world so the very first request already has results.

`scripts/build_hero.py` generates, ingests and analyses the world at development time and packs it into `hero.tar.gz`;
booting only unpacks it and writes the database rows, so the demo needs no compute and starts instantly. The world is
generated data (invented addresses, public-looking IPs used only as labels).
"""

from __future__ import annotations

import json
import logging
import shutil
import tarfile
from pathlib import Path

from sutradhar_api.config import Settings
from sutradhar_api.db import Database, utcnow
from sutradhar_api.jobs.handlers import HANDLERS
from sutradhar_api.jobs.queue import Claim
from sutradhar_api.models import Dataset, Job, Run

log = logging.getLogger("sutradhar.demo")
DEMO = Path(__file__).parent / "demo"
HERO_ARCHIVE = DEMO / "hero.tar.gz"
EVAL_JSON = DEMO / "eval.json"
HERO_DATASET, HERO_RUN = "ds_hero", "run_hero"


def _unpack(data_dir: Path) -> None:
    for folder in (f"datasets/{HERO_DATASET}", f"runs/{HERO_RUN}"):
        shutil.rmtree(data_dir / folder, ignore_errors=True)
    with tarfile.open(HERO_ARCHIVE, "r:gz") as tar:
        tar.extractall(
            data_dir, filter="data"
        )  # the "data" filter refuses absolute paths, links and traversal


def seed_hero(db: Database, settings: Settings) -> None:
    with db.read() as session:
        if session.get(Dataset, HERO_DATASET) is not None:
            return
    if not HERO_ARCHIVE.exists():
        log.warning("no hero archive: the demo world is not available (run scripts/build_hero.py)")
        return
    data = settings.data_dir
    _unpack(data)
    ds_dir, run_dir = data / "datasets" / HERO_DATASET, data / "runs" / HERO_RUN
    dataset_manifest = json.loads((ds_dir / "manifest.json").read_text(encoding="utf-8"))
    capability = json.loads((ds_dir / "xray.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    now = utcnow()
    with db.write() as s:
        s.add(
            Dataset(
                id=HERO_DATASET,
                name="Hero world (synthetic)",
                status="uploaded",
                source="generator",
                created_by=None,
                created_at=now,
            )
        )
        s.flush()
        s.add(
            Run(
                id=HERO_RUN,
                dataset_id=HERO_DATASET,
                status="running",
                config=run_manifest["config"],
                model_versions=run_manifest["config"].get("models", {}),
                refdata_versions={"watchlist": {"items": 1}},
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
            {"manifest": dataset_manifest, "capability": capability},
            data,
        )
        HANDLERS["run"].on_success(
            s,
            Claim("job_hero_run", "run", {"run_id": HERO_RUN, "dataset_id": HERO_DATASET}, 1, "seed"),
            {"manifest": run_manifest},
            data,
        )
        s.commit()
    log.info("hero world registered: %s", HERO_RUN)
