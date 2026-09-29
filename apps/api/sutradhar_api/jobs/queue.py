"""The durable job queue (blueprint §4.9 `jobs`, §9.1 "long work is always a job").

Claiming is one statement: pick the next queued job and mark it running. On PostgreSQL the pick uses
`FOR UPDATE SKIP LOCKED`, so concurrent workers never take the same job or wait on each other; on SQLite the
write transaction starts with `BEGIN IMMEDIATE`, which serialises claims. Every claim gets a fresh lock token;
heartbeats and completion only apply while the token still matches (fencing), so a worker that lost its job
to the stale-job rescuer can never overwrite the new owner's result.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sutradhar_api.db import Database, utcnow
from sutradhar_api.models import Job, JobEvent
from sutradhar_schemas.ids import new_id

TERMINAL = frozenset({"succeeded", "failed", "cancelled"})
STALE_AFTER = timedelta(seconds=90)


def idempotency_digest(user_id: str, key: str) -> str:
    """Keys are scoped per user and stored hashed, so one user's key never collides with another's."""
    return hashlib.sha256(f"{user_id}\x00{key}".encode()).hexdigest()


def find_idempotent(session: Session, user_id: str, key: str | None) -> Job | None:
    if not key:
        return None
    return session.scalar(select(Job).where(Job.idempotency_key == idempotency_digest(user_id, key)))


def add_event(session: Session, job_id: str, kind: str, data: dict[str, Any]) -> None:
    session.add(JobEvent(job_id=job_id, kind=kind, data=data, ts=utcnow()))


def enqueue(
    session: Session,
    *,
    kind: str,
    payload: dict[str, Any],
    created_by: str | None,
    idempotency_key: str | None = None,
    priority: int = 100,
    max_attempts: int = 1,
) -> Job:
    job = Job(
        id=new_id("job"),
        kind=kind,
        payload=payload,
        status="queued",
        priority=priority,
        attempts=0,
        max_attempts=max_attempts,
        cancel_requested=False,
        idempotency_key=idempotency_digest(created_by or "system", idempotency_key)
        if idempotency_key
        else None,
        created_by=created_by,
        created_at=utcnow(),
    )
    session.add(job)
    session.flush()
    add_event(session, job.id, "job.queued", {"job_id": job.id, "kind": kind})
    return job


@dataclass(frozen=True)
class Claim:
    job_id: str
    kind: str
    payload: dict[str, Any]
    attempts: int
    token: str


def claim(db: Database, worker_id: str) -> Claim | None:
    token = f"{worker_id}:{secrets.token_hex(6)}"
    now = utcnow()
    next_job = (
        select(Job.id)
        .where(Job.status == "queued")
        .order_by(Job.priority, Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    with db.write() as session:
        row = session.execute(
            update(Job)
            .where(Job.id == next_job, Job.status == "queued")
            .values(
                status="running",
                attempts=Job.attempts + 1,
                locked_by=token,
                locked_at=now,
                heartbeat_at=now,
                started_at=now,
            )
            .returning(Job.id, Job.kind, Job.payload, Job.attempts)
            .execution_options(synchronize_session=False)
        ).first()
        if row is None:
            session.rollback()
            return None
        add_event(session, row.id, "job.started", {"job_id": row.id, "attempt": row.attempts})
        session.commit()
        return Claim(
            job_id=row.id, kind=row.kind, payload=dict(row.payload), attempts=row.attempts, token=token
        )


def heartbeat(db: Database, job_id: str, token: str) -> tuple[bool, bool]:
    """Returns (still the owner, cancellation requested)."""
    with db.write() as session:
        row = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.locked_by == token, Job.status == "running")
            .values(heartbeat_at=utcnow())
            .returning(Job.cancel_requested)
            .execution_options(synchronize_session=False)
        ).first()
        session.commit()
    return (row is not None, bool(row[0]) if row is not None else False)


def mark_finished(
    session: Session,
    job_id: str,
    token: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> bool:
    """Inside the caller's transaction. False if this worker no longer owns the job (fenced out)."""
    if status not in TERMINAL:
        raise ValueError(f"not a terminal status: {status}")
    done = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.locked_by == token, Job.status == "running")
        .values(status=status, result=result, error=error, finished_at=utcnow(), locked_by=None)
        .execution_options(synchronize_session=False)
    )
    return done.rowcount == 1


def request_cancel(session: Session, job: Job) -> str:
    """Queued jobs are cancelled at once; running jobs are stopped by their worker at the next heartbeat."""
    if job.status == "queued":
        job.status, job.finished_at = "cancelled", utcnow()
        add_event(session, job.id, "job.cancelled", {"job_id": job.id})
        return "cancelled"
    if job.status == "running":
        job.cancel_requested = True
        add_event(session, job.id, "job.cancel_requested", {"job_id": job.id})
        return "cancelling"
    return job.status


def stale_jobs(session: Session, *, stale_after: timedelta = STALE_AFTER) -> list[Job]:
    cutoff = utcnow() - stale_after
    return list(
        session.scalars(
            select(Job).where(Job.status == "running", Job.heartbeat_at < cutoff).order_by(Job.id).limit(100)
        )
    )
