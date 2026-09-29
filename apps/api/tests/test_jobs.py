"""The job queue: atomic claims, fencing, stale-job rescue, cancellation, and the sandboxed job process."""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from apitest import add_user, bearer, login
from sqlalchemy import select, update

from sutradhar_api.config import Settings
from sutradhar_api.db import Database, utcnow
from sutradhar_api.jobs import queue
from sutradhar_api.jobs.worker import Worker
from sutradhar_api.models import Dataset, Job, JobEvent
from sutradhar_schemas.ids import new_id


def _dataset_job(db: Database, *, files: list[str] | None = None, max_attempts: int = 1) -> tuple[str, str]:
    dataset_id = new_id("ds")
    with db.write() as session:
        session.add(Dataset(id=dataset_id, name="t", status="uploaded", source="upload", created_at=utcnow()))
        session.flush()
        job = queue.enqueue(
            session,
            kind="ingest",
            payload={
                "dataset_id": dataset_id,
                "files": files or ["uploads/none.csv"],
                "profile": "canonical-v1",
            },
            created_by=None,
            max_attempts=max_attempts,
        )
        session.commit()
        return dataset_id, job.id


def test_claim_is_exclusive_and_fenced(database: Database) -> None:
    _, job_id = _dataset_job(database)
    first = queue.claim(database, "w1")
    assert first is not None and first.job_id == job_id
    assert queue.claim(database, "w2") is None
    assert queue.heartbeat(database, job_id, first.token) == (True, False)
    assert queue.heartbeat(database, job_id, "w2:forged") == (False, False)
    with database.write() as session:
        assert not queue.mark_finished(session, job_id, "w2:forged", status="succeeded")
        assert queue.mark_finished(session, job_id, first.token, status="succeeded", result={"ok": True})
        session.commit()


def test_concurrent_claims_never_share_a_job(database: Database) -> None:
    for _ in range(20):
        _dataset_job(database)
    claimed: list[str] = []
    lock = threading.Lock()

    def drain(worker: str) -> None:
        while (c := queue.claim(database, worker)) is not None:
            with lock:
                claimed.append(c.job_id)

    threads = [threading.Thread(target=drain, args=(f"w{i}",)) for i in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(claimed) == len(set(claimed)) == 20


def test_stale_jobs_are_requeued_then_failed(database: Database, settings: Settings) -> None:
    dataset_id, job_id = _dataset_job(database, max_attempts=2)
    worker = Worker(settings, database)
    for expected in ("queued", "failed"):
        claimed = queue.claim(database, "dead-worker")
        assert claimed is not None
        with database.write() as session:
            session.execute(
                update(Job).where(Job.id == job_id).values(heartbeat_at=utcnow() - timedelta(minutes=10))
            )
            session.commit()
        worker.maintain()
        with database.read() as session:
            assert session.get(Job, job_id).status == expected  # type: ignore[union-attr]
    with database.read() as session:
        assert session.get(Dataset, dataset_id).status == "failed"  # type: ignore[union-attr]


def test_cancel_queued_job(client, tiny_csv: bytes) -> None:  # type: ignore[no-untyped-def]

    owner = bearer(login(client, add_user(client)))
    body = client.post(
        "/api/v1/datasets", headers=owner, files={"files": ("t.csv", tiny_csv[:2000], "text/csv")}
    ).json()
    job_id, dataset_id = body["job"]["id"], body["dataset"]["id"]
    assert client.post(f"/api/v1/jobs/{job_id}/cancel", headers=owner).json()["status"] == "cancelled"
    assert client.post(f"/api/v1/jobs/{job_id}/cancel", headers=owner).status_code == 409
    assert client.get(f"/api/v1/datasets/{dataset_id}", headers=owner).json()["status"] == "failed"
    other = bearer(login(client, add_user(client, "lead")))
    assert client.post(f"/api/v1/jobs/{job_id}/cancel", headers=other).status_code in (403, 409)


@pytest.mark.security
def test_job_payload_cannot_escape_the_data_directory(database: Database, settings: Settings) -> None:
    secret = settings.data_dir.parent / "outside.csv"
    secret.write_text("timestamp,txid\n", encoding="utf-8")
    dataset_id, job_id = _dataset_job(database, files=["../outside.csv"])
    assert Worker(settings, database).run_once()
    with database.read() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert "PermissionError" in (job.error or "")
        assert str(settings.data_dir) not in (job.error or "")
        assert session.get(Dataset, dataset_id).status == "failed"  # type: ignore[union-attr]


def test_failed_job_reports_a_clean_error(database: Database, settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "uploads").mkdir(exist_ok=True)
    (settings.data_dir / "uploads" / "bad.csv").write_bytes(b"\xff\xfe\x00garbage")
    _, job_id = _dataset_job(database, files=["uploads/bad.csv"])
    assert Worker(settings, database).run_once()
    with database.read() as session:
        job = session.get(Job, job_id)
        kinds = session.scalars(
            select(JobEvent.kind).where(JobEvent.job_id == job_id).order_by(JobEvent.id)
        ).all()
    assert job is not None
    assert kinds[0] == "job.queued"
    assert "Traceback" not in (job.error or "")
