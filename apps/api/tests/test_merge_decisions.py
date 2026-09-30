"""Analysts accept or reject merge suggestions: lead role only, audited, order-independent, replaceable."""

from __future__ import annotations

import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient
from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.jobs.worker import Worker
from sutradhar_api.models import AuditLog


@pytest.fixture
def run_id(client: TestClient, tiny_csv: bytes) -> tuple[str, dict[str, str]]:
    headers = bearer(login(client, add_user(client, "lead")))
    worker = Worker(client.app.state.settings, client.app.state.db)
    up = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv, "text/csv")}
    ).json()
    while not worker.run_once():
        pass
    run = client.post("/api/v1/runs", headers=headers, json={"dataset_id": up["dataset"]["id"]}).json()
    while client.get(f"/api/v1/jobs/{run['job']['id']}", headers=headers).json()["status"] not in (
        "succeeded",
        "failed",
    ):
        worker.run_once()
    return run["run"]["id"], headers


def _body(run: str, decision: str = "accept", a: str = "clusterAAAA1", b: str = "clusterBBBB2") -> dict:
    return {"run_id": run, "a": a, "b": b, "decision": decision, "reason": "same operator, shared IP"}


def test_lead_decides_and_it_is_audited(client: TestClient, run_id) -> None:
    run, headers = run_id
    response = client.post("/api/v1/merge-decisions", headers=headers, json=_body(run))
    assert response.status_code == 201
    assert response.json()["decision"] == "accept"
    with client.app.state.db.read() as session:
        assert "merge.accept" in session.scalars(select(AuditLog.action)).all()
        assert audit.verify(session).ok


def test_pair_order_does_not_matter_and_later_decision_replaces(client: TestClient, run_id) -> None:
    run, headers = run_id
    client.post("/api/v1/merge-decisions", headers=headers, json=_body(run, "accept"))
    swapped = client.post(
        "/api/v1/merge-decisions",
        headers=headers,
        json=_body(run, "reject", a="clusterBBBB2", b="clusterAAAA1"),
    )
    assert swapped.status_code == 201
    listed = client.get("/api/v1/merge-decisions", headers=headers).json()["items"]
    assert len(listed) == 1 and listed[0]["decision"] == "reject"


@pytest.mark.security
@pytest.mark.parametrize("role", ["analyst", "auditor", "admin"])
def test_only_lead_analysts_can_decide(client: TestClient, run_id, role: str) -> None:
    run, _ = run_id
    other = bearer(login(client, add_user(client, role)))
    assert client.post("/api/v1/merge-decisions", headers=other, json=_body(run)).status_code == 403


@pytest.mark.security
def test_decisions_validate_input(client: TestClient, run_id) -> None:
    run, headers = run_id
    assert (
        client.post("/api/v1/merge-decisions", headers=headers, json=_body(run, "maybe")).status_code == 422
    )
    assert (
        client.post(
            "/api/v1/merge-decisions", headers=headers, json=_body(run, a="samesamesame", b="samesamesame")
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/merge-decisions", headers=headers, json={**_body(run), "reason": ""}).status_code
        == 422
    )
    assert (
        client.post("/api/v1/merge-decisions", headers=headers, json={**_body(run), "extra": 1}).status_code
        == 422
    )
    assert client.post("/api/v1/merge-decisions", headers=headers, json=_body("run_nope")).status_code == 404
