"""Datasets: multipart upload → 202 + ingest job (I01 to I06); list and detail with the X-ray."""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from sutradhar_api import audit
from sutradhar_api.access import can_see, scoped
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.config import Settings
from sutradhar_api.db import utcnow
from sutradhar_api.deps import ReadDB, rate_limit, require
from sutradhar_api.jobs.queue import enqueue, find_idempotent
from sutradhar_api.models import Dataset, DatasetFile, Job
from sutradhar_api.pagination import Cursor, Limit, Page, cursor_time, decode_cursor, encode_cursor
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import DatasetAccepted, DatasetDetail, DatasetFileOut, DatasetOut, JobOut
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1", tags=["datasets"])
FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "csv",
    ".json": "json",
    ".ndjson": "ndjson",
    ".jsonl": "ndjson",
    ".xml": "xml",
}
PROFILES = {
    "csv": "canonical-v1",
    "tsv": "canonical-v1",
    "json": "canonical-json-v1",
    "ndjson": "canonical-ndjson-v1",
    "xml": "canonical-xml-v1",
}
MAX_FILES = 10
DEMO_MAX_ACTIVE_JOBS = 2
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
CHUNK = 1 << 20


def safe_filename(raw: str | None) -> str:
    """Basename only, conservative alphabet, bounded length: the stored name can never address a path."""
    base = PurePosixPath((raw or "upload").replace("\\", "/")).name
    base = _UNSAFE.sub("_", base).strip("._-") or "upload"
    stem, dot, ext = base.rpartition(".")
    return f"{stem[:80]}.{ext[:8]}" if dot and stem else base[:90]


@dataclass(frozen=True)
class Saved:
    file_id: str
    filename: str
    relative: str
    format: str
    sha256: str
    bytes: int


async def _save(files: list[UploadFile], settings: Settings, dataset_id: str) -> list[Saved]:
    dest = settings.data_dir / "uploads" / dataset_id
    dest.mkdir(parents=True, exist_ok=False)
    cap, total, lines, saved = settings.upload_cap_bytes, 0, 0, []
    for upload in files:
        name = safe_filename(upload.filename)
        fmt = FORMATS.get(Path(name).suffix.lower())
        if fmt is None:
            raise Problem(415, "unsupported_format", f"{name}: upload CSV, TSV, JSON, NDJSON or XML files")
        file_id = new_id("file")
        path = dest / f"{file_id}__{name}"
        digest, size = hashlib.sha256(), 0
        with path.open("xb") as out:
            while chunk := await upload.read(CHUNK):
                size += len(chunk)
                total += len(chunk)
                if total > cap:
                    raise Problem(
                        413, "too_large", f"uploads are limited to {cap // (1024 * 1024)} MB in total"
                    )
                if settings.is_demo:
                    lines += chunk.count(b"\n")
                    if lines > settings.demo_upload_max_rows + len(files):
                        raise Problem(
                            413,
                            "too_many_rows",
                            f"demo uploads are limited to {settings.demo_upload_max_rows} rows",
                        )
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise Problem(400, "empty_file", f"{name} is empty")
        saved.append(Saved(file_id, name, f"uploads/{dataset_id}/{path.name}", fmt, digest.hexdigest(), size))
    return saved


def _record(
    request: Request, principal: Principal, dataset_id: str, name: str, saved: list[Saved], *, key: str | None
) -> DatasetAccepted:
    settings: Settings = request.app.state.settings
    with request.app.state.db.write() as db:
        existing = find_idempotent(db, principal.user.id, key)
        if existing is not None:
            db.rollback()
            raise _ReplayError(existing.id)
        now = utcnow()
        dataset = Dataset(
            id=dataset_id,
            name=name,
            status="uploaded",
            source="upload",
            bytes=sum(s.bytes for s in saved),
            expires_at=now + timedelta(minutes=settings.demo_upload_ttl_min) if settings.is_demo else None,
            created_by=principal.user.id,
            created_at=now,
        )
        db.add(dataset)
        db.flush()
        for s in saved:
            db.add(
                DatasetFile(
                    id=s.file_id,
                    dataset_id=dataset_id,
                    filename=s.filename,
                    format=s.format,
                    sha256=s.sha256,
                    bytes=s.bytes,
                    created_at=now,
                )
            )
        job = enqueue(
            db,
            kind="ingest",
            payload={
                "dataset_id": dataset_id,
                "files": [s.relative for s in saved],
                "profile": "canonical-v1",
            },
            created_by=principal.user.id,
            idempotency_key=key,
        )
        audit.append(
            db,
            actor_id=principal.user.id,
            actor_role=principal.role,
            action="dataset.upload",
            target_kind="dataset",
            target_ref=dataset_id,
            payload={"files": [{"name": s.filename, "sha256": s.sha256, "bytes": s.bytes} for s in saved]},
        )
        db.commit()
        return DatasetAccepted(dataset=DatasetOut.model_validate(dataset), job=JobOut.model_validate(job))


class _ReplayError(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(job_id)
        self.job_id = job_id


def _replayed(request: Request, principal: Principal, job_id: str) -> DatasetAccepted:
    with request.app.state.db.read() as db:
        job = db.get(Job, job_id)
        dataset = db.get(Dataset, job.payload.get("dataset_id")) if job else None
        if (
            job is None
            or dataset is None
            or job.kind != "ingest"
            or not can_see(dataset.created_by, principal)
        ):
            raise Problem(
                409, "idempotency_conflict", "this Idempotency-Key was used for a different request"
            )
        return DatasetAccepted(dataset=DatasetOut.model_validate(dataset), job=JobOut.model_validate(job))


def _check_capacity(request: Request, principal: Principal) -> None:
    if not request.app.state.settings.is_demo:
        return
    with request.app.state.db.read() as db:
        active = db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.created_by == principal.user.id, Job.status.in_(("queued", "running")))
        )
    if (active or 0) >= DEMO_MAX_ACTIVE_JOBS:
        raise Problem(429, "busy", "wait for your current jobs to finish before starting another")


@router.post(
    "/datasets",
    status_code=202,
    dependencies=[rate_limit("upload", limit=5, window_s=3600, demo_only=True)],
)
async def upload_dataset(
    request: Request,
    principal: Annotated[Principal, require(Action.DATASET_UPLOAD)],
    files: Annotated[list[UploadFile], File(description="One to ten CSV/TSV files in the canonical layout.")],
    name: Annotated[str | None, Form(max_length=120)] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> DatasetAccepted:
    if idempotency_key:
        with request.app.state.db.read() as db:
            existing = find_idempotent(db, principal.user.id, idempotency_key)
        if existing is not None:
            return await run_in_threadpool(_replayed, request, principal, existing.id)
    if (
        len(
            {PROFILES.get(FORMATS.get(Path(safe_filename(f.filename)).suffix.lower(), ""), "") for f in files}
        )
        > 1
    ):
        raise Problem(400, "mixed_formats", "upload files of one format at a time")
    if not 1 <= len(files) <= MAX_FILES:
        raise Problem(400, "file_count", f"upload between 1 and {MAX_FILES} files")
    await run_in_threadpool(_check_capacity, request, principal)
    settings: Settings = request.app.state.settings
    dataset_id = new_id("ds")
    try:
        saved = await _save(files, settings, dataset_id)
        label = (name or "").strip() or Path(saved[0].filename).stem
        return await run_in_threadpool(
            _record, request, principal, dataset_id, label[:120], saved, key=idempotency_key
        )
    except _ReplayError as replay:
        shutil.rmtree(settings.data_dir / "uploads" / dataset_id, ignore_errors=True)
        return await run_in_threadpool(_replayed, request, principal, replay.job_id)
    except BaseException:
        shutil.rmtree(settings.data_dir / "uploads" / dataset_id, ignore_errors=True)
        raise


def _visible_dataset(db: Session, dataset_id: str, principal: Principal) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or not can_see(dataset.created_by, principal):
        raise Problem(404, "not_found", "no such dataset")
    return dataset


@router.get("/datasets")
def list_datasets(
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[DatasetOut]:
    stmt = scoped(select(Dataset), Dataset.created_by, principal)
    after = decode_cursor(cursor, (str, str))
    if after is not None:
        at = cursor_time(after[0])
        stmt = stmt.where(or_(Dataset.created_at < at, and_(Dataset.created_at == at, Dataset.id < after[1])))
    rows = list(db.scalars(stmt.order_by(Dataset.created_at.desc(), Dataset.id.desc()).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor([rows[-1].created_at.isoformat(), rows[-1].id]) if more else None
    return Page[DatasetOut](items=[DatasetOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB
) -> DatasetDetail:
    dataset = _visible_dataset(db, dataset_id, principal)
    files = db.scalars(
        select(DatasetFile).where(DatasetFile.dataset_id == dataset.id).order_by(DatasetFile.filename)
    )
    detail = DatasetDetail.model_validate(
        {**DatasetOut.model_validate(dataset).model_dump(), "xray": dataset.xray, "files": []}
    )
    detail.files = [DatasetFileOut.model_validate(f) for f in files]
    return detail


@router.get("/datasets/{dataset_id}/rejects")
def dataset_rejects(
    dataset_id: str,
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    rule: Annotated[str | None, Query(max_length=8)] = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[dict]:
    """Rows the ingest refused, each with its rule id and reason (values are text, truncated to 200 characters)."""
    import duckdb

    _visible_dataset(db, dataset_id, principal)
    path = request.app.state.settings.data_dir / "datasets" / dataset_id / "dataset.duckdb"
    if not path.exists():
        return Page[dict](items=[], next_cursor=None)
    after = decode_cursor(cursor, (int,))
    offset = after[0] if after else 0
    con = duckdb.connect(str(path), read_only=True)
    try:
        where, params = ("WHERE rule = ?", [rule]) if rule else ("", [])
        rows = con.execute(
            f'SELECT file_id, row_no, rule, "field", value, message FROM rejects {where} ORDER BY file_id, row_no, rule LIMIT ? OFFSET ?',  # noqa: S608
            [*params, limit + 1, offset],
        ).fetchall()
    finally:
        con.close()
    more, rows = len(rows) > limit, rows[:limit]
    items = [
        dict(zip(("file_id", "row_no", "rule", "field", "value", "message"), r, strict=True)) for r in rows
    ]
    return Page[dict](items=items, next_cursor=encode_cursor([offset + limit]) if more else None)
