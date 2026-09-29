"""P0.5 done-when: upload → job → run → leads through the API, with live SSE progress; plus the demo TTL purge."""

from __future__ import annotations

import json
import time
from datetime import timedelta
from typing import Any

import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from sutradhar_api import audit
from sutradhar_api.app import create_app
from sutradhar_api.db import utcnow
from sutradhar_api.jobs import maintenance
from sutradhar_api.jobs.worker import Worker
from sutradhar_api.models import AuditLog, Dataset


def _sse(
    client: TestClient, headers: dict[str, str], job_id: str, last: int | None = None
) -> list[dict[str, Any]]:
    extra = {"Last-Event-ID": str(last)} if last is not None else {}
    events: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    with client.stream("GET", f"/api/v1/events?topics=job:{job_id}", headers={**headers, **extra}) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        for line in stream.iter_lines():
            if line.startswith("event: "):
                current["event"] = line[7:]
            elif line.startswith("data: "):
                current["data"] = json.loads(line[6:])
            elif line.startswith("id: "):
                current["id"] = int(line[4:])
            elif line == "" and current:
                events.append(current)
                current = {}
    return events


def _wait(client: TestClient, headers: dict[str, str], job_id: str, worker: Worker | None) -> dict[str, Any]:
    for _ in range(240):
        if worker is not None:
            worker.run_once()
        job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
        if job["status"] in ("succeeded", "failed", "cancelled"):
            return job
        time.sleep(0.25)
    raise AssertionError("job did not finish")


def test_upload_ingest_run_leads(client: TestClient, tiny_csv: bytes) -> None:
    headers = bearer(login(client, add_user(client, "analyst")))
    worker = Worker(client.app.state.settings, client.app.state.db)

    upload = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("traffic.csv", tiny_csv, "text/csv")}
    )
    assert upload.status_code == 202
    ingest = _wait(client, headers, upload.json()["job"]["id"], worker)
    assert ingest["status"] == "succeeded", ingest
    dataset = client.get(f"/api/v1/datasets/{upload.json()['dataset']['id']}", headers=headers).json()
    assert dataset["status"] == "normalised"
    assert dataset["reject_count"] == 0
    assert dataset["xray"]["network"]["observation_model"] == "vantage"

    started = client.post("/api/v1/runs", headers=headers, json={"dataset_id": dataset["id"]})
    assert started.status_code == 202, started.text
    run_id, job_id = started.json()["run"]["id"], started.json()["job"]["id"]
    assert _wait(client, headers, job_id, worker)["status"] == "succeeded"

    events = _sse(client, headers, job_id)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "job.queued"
    assert "job.progress" in kinds
    assert kinds[-2:] == ["run.published", "job.completed"]
    ids = [e["id"] for e in events]
    assert ids == sorted(ids)
    resumed = _sse(client, headers, job_id, last=ids[2])
    assert [e["id"] for e in resumed] == ids[3:]

    run = client.get(f"/api/v1/runs/{run_id}", headers=headers).json()
    assert run["status"] == "published"
    assert len(run["result_digest"]) == 64
    leads = client.get(f"/api/v1/runs/{run_id}/leads", headers=headers, params={"limit": 5}).json()
    assert leads["items"], "the stub ranker flags peel-shaped transactions"
    first = leads["items"][0]
    assert first["calibrated"] is False and first["model_version"] == "rules@0-stub"
    assert first["state"]["status"] == "NEW"
    assert first["families"]
    detail = client.get(f"/api/v1/leads/{first['id']}", headers=headers).json()
    assert detail["reasons"] and detail["reasons"][0]["text"]
    priorities = [lead["priority"] for lead in leads["items"]]
    assert priorities == sorted(priorities, reverse=True)

    with client.app.state.db.read() as session:
        actions = session.scalars(select(AuditLog.action).order_by(AuditLog.seq)).all()
        assert audit.verify(session).ok
    for action in ("auth.login", "dataset.upload", "dataset.ingested", "run.start", "run.published"):
        assert action in actions


def test_same_dataset_twice_gives_the_same_result_digest(client: TestClient, tiny_csv: bytes) -> None:
    headers = bearer(login(client, add_user(client, "analyst")))
    worker = Worker(client.app.state.settings, client.app.state.db)
    upload = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv, "text/csv")}
    ).json()
    _wait(client, headers, upload["job"]["id"], worker)
    digests = []
    for _ in range(2):
        run = client.post(
            "/api/v1/runs", headers=headers, json={"dataset_id": upload["dataset"]["id"]}
        ).json()
        _wait(client, headers, run["job"]["id"], worker)
        digests.append(
            client.get(f"/api/v1/runs/{run['run']['id']}", headers=headers).json()["result_digest"]
        )
    assert digests[0] == digests[1]


def test_run_needs_a_ready_dataset(client: TestClient, tiny_csv: bytes) -> None:
    headers = bearer(login(client, add_user(client, "analyst")))
    upload = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv[:3000], "text/csv")}
    )
    response = client.post(
        "/api/v1/runs", headers=headers, json={"dataset_id": upload.json()["dataset"]["id"]}
    )
    assert response.status_code == 409
    assert client.post("/api/v1/runs", headers=headers, json={"dataset_id": "ds_nope"}).status_code == 404


def test_embedded_worker_runs_jobs(make_settings, tiny_csv: bytes) -> None:  # type: ignore[no-untyped-def]
    with TestClient(create_app(make_settings(app_mode="demo", embedded_worker=True))) as demo:
        assert demo.get("/api/ready").json()["checks"]["worker"] is True
        visitor = bearer(demo.post("/api/v1/auth/demo").json())
        upload = demo.post(
            "/api/v1/datasets", headers=visitor, files={"files": ("t.csv", tiny_csv, "text/csv")}
        )
        assert _wait(demo, visitor, upload.json()["job"]["id"], None)["status"] == "succeeded"


@pytest.mark.security
def test_demo_upload_ttl_purge(make_settings, tiny_csv: bytes) -> None:
    """I19: expired demo uploads disappear with their runs and files; the audit chain records the purge."""
    demo_client = TestClient(create_app(make_settings(app_mode="demo", demo_upload_max_mb=25)))
    demo_client.__enter__()
    visitor = bearer(demo_client.post("/api/v1/auth/demo").json())
    settings, db = demo_client.app.state.settings, demo_client.app.state.db
    worker = Worker(settings, db)
    upload = demo_client.post(
        "/api/v1/datasets", headers=visitor, files={"files": ("t.csv", tiny_csv, "text/csv")}
    )
    dataset_id = upload.json()["dataset"]["id"]
    _wait(demo_client, visitor, upload.json()["job"]["id"], worker)
    run = demo_client.post("/api/v1/runs", headers=visitor, json={"dataset_id": dataset_id}).json()
    _wait(demo_client, visitor, run["job"]["id"], worker)
    assert (settings.data_dir / "datasets" / dataset_id / "dataset.duckdb").exists()

    with db.write() as session:
        session.execute(
            update(Dataset).where(Dataset.id == dataset_id).values(expires_at=utcnow() - timedelta(minutes=1))
        )
        session.commit()
    assert maintenance.purge_expired(db, settings) == 1

    assert demo_client.get(f"/api/v1/datasets/{dataset_id}", headers=visitor).status_code == 404
    assert demo_client.get(f"/api/v1/runs/{run['run']['id']}", headers=visitor).status_code == 404
    for folder in ("uploads", "datasets"):
        assert not (settings.data_dir / folder / dataset_id).exists()
    assert not (settings.data_dir / "runs" / run["run"]["id"]).exists()
    with db.read() as session:
        assert "dataset.purged" in session.scalars(select(AuditLog.action)).all()
        assert audit.verify(session).ok
