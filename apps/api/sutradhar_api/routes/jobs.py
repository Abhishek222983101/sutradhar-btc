"""Job status, cancellation and the live progress stream (Server-Sent Events, §9.4).

The stream authenticates with the Authorization header (the web client uses fetch-event-source), never a
token in the URL. It resumes after `Last-Event-ID`, sends a keep-alive comment every 15 s, and ends once every
watched job has finished and its last events are delivered.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.access import can_see_job
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import Database
from sutradhar_api.deps import ReadDB, WriteDB, require
from sutradhar_api.jobs.queue import TERMINAL, request_cancel
from sutradhar_api.models import Job, JobEvent
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import JobOut
from sutradhar_schemas.ids import is_id

router = APIRouter(prefix="/api/v1", tags=["jobs"])
MAX_TOPICS = 20
STREAM_MAX_S = 1800
POLL_S = 0.5


def _visible_job(db: Any, job_id: str, principal: Principal) -> Job:
    job = db.get(Job, job_id)
    if job is None or not can_see_job(job.created_by, principal):
        raise Problem(404, "not_found", "no such job")
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB) -> JobOut:
    return JobOut.model_validate(_visible_job(db, job_id, principal))


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str, principal: Annotated[Principal, require(Action.JOB_CANCEL)], db: WriteDB
) -> JobOut:
    job = _visible_job(db, job_id, principal)
    if job.created_by != principal.user.id and principal.role != "admin":
        raise Problem(403, "forbidden", "only the job's owner or an administrator can cancel it")
    if job.status in TERMINAL:
        raise Problem(409, "job_finished", f"the job has already {job.status}")
    outcome = request_cancel(db, job)
    if outcome == "cancelled":
        from sutradhar_api.jobs.handlers import HANDLERS

        handler = HANDLERS.get(job.kind)
        if handler is not None:
            handler.on_failure(db, job.payload, "cancelled by user")
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="job.cancel",
        target_kind="job",
        target_ref=job.id,
        payload={"outcome": outcome},
    )
    db.commit()
    return JobOut.model_validate(job)


def _topics(raw: str, principal: Principal, database: Database) -> list[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts or len(parts) > MAX_TOPICS:
        raise Problem(400, "bad_topics", f"subscribe to 1 to {MAX_TOPICS} topics like job:<id>")
    job_ids = []
    for part in parts:
        kind, _, ident = part.partition(":")
        if kind != "job" or not is_id(ident, "job"):
            raise Problem(400, "bad_topics", "topics look like job:<job id>")
        job_ids.append(ident)
    with database.read() as db:
        for job_id in job_ids:
            _visible_job(db, job_id, principal)
    return job_ids


def _poll(database: Database, job_ids: list[str], after: int) -> tuple[list[JobEvent], bool]:
    with database.read() as db:
        events = list(
            db.scalars(
                select(JobEvent)
                .where(JobEvent.job_id.in_(job_ids), JobEvent.id > after)
                .order_by(JobEvent.id)
                .limit(500)
            )
        )
        statuses = db.scalars(select(Job.status).where(Job.id.in_(job_ids))).all()
    return events, all(s in TERMINAL for s in statuses)


@router.get("/events", response_class=EventSourceResponse)
async def events(
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    topics: Annotated[str, Query(max_length=1200, description="Comma-separated, e.g. job:job_01J…")],
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
) -> AsyncIterator[ServerSentEvent]:
    database: Database = request.app.state.db
    job_ids = await run_in_threadpool(_topics, topics, principal, database)
    after = last_event_id or 0
    started = time.monotonic()
    yield ServerSentEvent(comment="connected", retry=3000)
    while not await request.is_disconnected():
        batch, done = await run_in_threadpool(_poll, database, job_ids, after)
        for event in batch:
            after = event.id
            yield ServerSentEvent(data=event.data, event=event.kind, id=str(event.id))
        if (done and not batch) or time.monotonic() - started > STREAM_MAX_S:
            return
        if not batch:
            await asyncio.sleep(POLL_S)
