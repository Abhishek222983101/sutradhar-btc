"""What each job kind means for the app database. These run in the worker, inside the same transaction that
marks the job finished, so a dataset or run is never "done" without its job (and its audit entry) being done.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import duckdb
from sqlalchemy import insert
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from sutradhar_api import audit
from sutradhar_api.db import utcnow
from sutradhar_api.jobs.queue import Claim, add_event
from sutradhar_api.models import Dataset, Lead, LeadState, Run
from sutradhar_schemas.ids import new_id

LEAD_SQL = (
    "SELECT lead_key, type, subject_kind, subject_ref, p, grade, priority, families, reasons, value_at_risk_sats,"
    " last_activity_us, title, summary, calibrated, model_version FROM lead ORDER BY lead_i"
)


class Handler(Protocol):
    def on_progress(self, session: Session, claim: Claim, stage: str) -> None: ...
    def on_success(
        self, session: Session, claim: Claim, result: dict[str, Any], data_dir: Path
    ) -> dict[str, Any]: ...
    def on_failure(self, session: Session, payload: dict[str, Any], error: str) -> None: ...


class IngestHandler:
    def on_progress(self, session: Session, claim: Claim, stage: str) -> None:
        return None

    def on_success(
        self, session: Session, claim: Claim, result: dict[str, Any], data_dir: Path
    ) -> dict[str, Any]:
        dataset = session.get(Dataset, claim.payload["dataset_id"])
        if dataset is None:
            raise LookupError("dataset no longer exists")
        manifest, capability = result["manifest"], result["capability"]
        dataset.status = "normalised"
        dataset.raw_digest = manifest["raw_digest"]
        dataset.normalised_digest = manifest["normalised_digest"]
        dataset.xray = capability
        dataset.row_count = capability["rows"]
        dataset.reject_count = capability["quality"]["rejects"]
        summary = {
            "dataset_id": dataset.id,
            "rows": capability["rows"],
            "transactions": capability["txs"],
            "rejects": capability["quality"]["rejects"],
            "observation_model": capability["network"]["observation_model"],
            "normalised_digest": manifest["normalised_digest"],
        }
        audit.append(
            session,
            actor_id=None,
            actor_role=audit.SYSTEM,
            action="dataset.ingested",
            target_kind="dataset",
            target_ref=dataset.id,
            payload={**summary, "job_id": claim.job_id},
        )
        add_event(session, claim.job_id, "dataset.status", {"dataset_id": dataset.id, "status": "normalised"})
        return summary

    def on_failure(self, session: Session, payload: dict[str, Any], error: str) -> None:
        dataset = session.get(Dataset, payload["dataset_id"])
        if dataset is not None and dataset.status != "normalised":
            dataset.status, dataset.error = "failed", error
            audit.append(
                session,
                actor_id=None,
                actor_role=audit.SYSTEM,
                action="dataset.failed",
                target_kind="dataset",
                target_ref=dataset.id,
                payload={"error": error[:200]},
            )


def _upsert_lead_states(session: Session, keys: list[str], run_id: str) -> None:
    if not keys:
        return
    dialect = session.get_bind().dialect.name
    ins = postgresql.insert(LeadState) if dialect == "postgresql" else sqlite.insert(LeadState)
    now = utcnow()
    rows = [
        {
            "lead_key": k,
            "status": "NEW",
            "last_seen_run_id": run_id,
            "changed_since_review": False,
            "updated_at": now,
        }
        for k in keys
    ]
    for start in range(0, len(rows), 5000):
        stmt = ins.values(rows[start : start + 5000])
        session.execute(
            stmt.on_conflict_do_update(index_elements=["lead_key"], set_={"last_seen_run_id": run_id})
        )


def _micros(value: int | None) -> datetime | None:
    return None if value is None else datetime.fromtimestamp(value / 1_000_000, tz=UTC)


class RunHandler:
    def on_progress(self, session: Session, claim: Claim, stage: str) -> None:
        run = session.get(Run, claim.payload["run_id"])
        if run is not None and stage.startswith("E") and run.stage != stage:
            run.stage = stage
            run.status = "running"

    def on_success(
        self, session: Session, claim: Claim, result: dict[str, Any], data_dir: Path
    ) -> dict[str, Any]:
        run = session.get(Run, claim.payload["run_id"])
        if run is None:
            raise LookupError("run no longer exists")
        manifest = result["manifest"]
        con = duckdb.connect(str(data_dir / "runs" / run.id / "run.duckdb"), read_only=True)
        try:
            rows = con.execute(LEAD_SQL).fetchall()
        finally:
            con.close()
        now = utcnow()
        leads = [
            {
                "id": new_id("ld"),
                "run_id": run.id,
                "lead_key": r[0],
                "type": r[1],
                "subject_kind": r[2],
                "subject_ref": r[3],
                "p": float(r[4]),
                "grade": r[5],
                "priority": float(r[6]),
                "families": _json(r[7]),
                "reasons": _json(r[8]),
                "value_at_risk_sats": int(r[9]),
                "last_activity_at": _micros(r[10]),
                "title": r[11],
                "summary": r[12],
                "calibrated": bool(r[13]),
                "model_version": r[14],
                "created_at": now,
            }
            for r in rows
        ]
        for start in range(0, len(leads), 5000):
            session.execute(insert(Lead), leads[start : start + 5000])
        _upsert_lead_states(session, [lead["lead_key"] for lead in leads], run.id)
        run.status, run.stage, run.finished_at = "published", None, now
        run.manifest, run.result_digest = manifest, manifest["result_digest"]
        summary = {"run_id": run.id, "leads": len(leads), "result_digest": manifest["result_digest"]}
        audit.append(
            session,
            actor_id=None,
            actor_role=audit.SYSTEM,
            action="run.published",
            target_kind="run",
            target_ref=run.id,
            payload={**summary, "job_id": claim.job_id},
        )
        add_event(
            session,
            claim.job_id,
            "run.published",
            {"run_id": run.id, "new": len(leads), "changed": 0, "gone": 0},
        )
        return summary

    def on_failure(self, session: Session, payload: dict[str, Any], error: str) -> None:
        run = session.get(Run, payload["run_id"])
        if run is not None and run.status != "published":
            run.status, run.error, run.finished_at = "failed", error, utcnow()
            audit.append(
                session,
                actor_id=None,
                actor_role=audit.SYSTEM,
                action="run.failed",
                target_kind="run",
                target_ref=run.id,
                payload={"error": error[:200]},
            )


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


HANDLERS: dict[str, Handler] = {"ingest": IngestHandler(), "run": RunHandler()}
