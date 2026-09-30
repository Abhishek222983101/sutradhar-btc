"""Leads end to end: explanations, subgraph bounds, filters, triage rules, demo isolation, carry-over and diffs."""

from __future__ import annotations

from typing import Any

import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient
from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.jobs.worker import Worker
from sutradhar_api.models import AuditLog


def _finish(client: TestClient, headers: dict[str, str], job_id: str, worker: Worker) -> None:
    for _ in range(600):
        if client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()["status"] in ("succeeded", "failed"):
            return
        worker.run_once()
    raise AssertionError("job did not finish")


@pytest.fixture
def analysed(client: TestClient, tiny_csv: bytes) -> tuple[dict[str, str], str, str, Worker]:
    headers = bearer(login(client, add_user(client, "lead")))
    worker = Worker(client.app.state.settings, client.app.state.db)
    up = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv, "text/csv")}
    ).json()
    _finish(client, headers, up["job"]["id"], worker)
    run = client.post("/api/v1/runs", headers=headers, json={"dataset_id": up["dataset"]["id"]}).json()
    _finish(client, headers, run["job"]["id"], worker)
    return headers, up["dataset"]["id"], run["run"]["id"], worker


def _leads(client: TestClient, headers: dict[str, str], run: str, **params: Any) -> list[dict[str, Any]]:
    return client.get(f"/api/v1/runs/{run}/leads", headers=headers, params={"limit": 200, **params}).json()[
        "items"
    ]


def test_every_lead_has_reason_grade_calibrated_p(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    leads = _leads(client, headers, run)
    assert leads
    for lead in leads:
        detail = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()
        assert 0 <= lead["p"] <= 1 and lead["grade"] in "ABC"
        assert lead["families"] and detail["reasons"]  # I6
        assert all(r["text"] for r in detail["reasons"])
        if lead["type"] == "ACTOR":
            assert lead["calibrated"] is True


def test_explanation_has_all_parts(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    actor = next(x for x in _leads(client, headers, run, type="ACTOR"))
    e = client.get(f"/api/v1/leads/{actor['id']}/explanation", headers=headers).json()
    assert set(e) == {"reasons", "opposing", "counterfactual", "priority", "provenance"}
    assert set(e["priority"]) == {"p", "value_factor", "recency_factor", "actionable_factor"}
    assert e["provenance"]["calibrated"] is True and e["provenance"]["model"]
    for cf in e["counterfactual"]:
        assert cf["p_after"] <= cf["p_before"] + 1e-6  # removing evidence never raises the score


def test_priority_formula(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    for lead in _leads(client, headers, run, type="ACTOR"):
        pr = client.get(f"/api/v1/leads/{lead['id']}/explanation", headers=headers).json()["priority"]
        expected = pr["p"] * pr["value_factor"] * pr["recency_factor"] * pr["actionable_factor"]
        assert lead["priority"] == pytest.approx(expected, abs=1e-3)


def test_subgraph_bounded_and_edges_carry_evidence(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    for lead in _leads(client, headers, run, type="ACTOR")[:5]:
        g = client.get(f"/api/v1/leads/{lead['id']}/subgraph", headers=headers).json()
        assert 0 < len(g["nodes"]) <= 150
        ids = {n["id"] for n in g["nodes"]}
        for edge in g["edges"]:
            assert edge["source"] in ids and edge["target"] in ids  # I2: an edge names its ends,
            assert (
                edge["method"] and 0 <= edge["confidence"] <= 1 and edge["evidence_refs"]
            )  # method, confidence, evidence


def test_services_and_victims_are_never_actor_leads(client: TestClient, analysed) -> None:
    import duckdb

    headers, _, run, _ = analysed
    con = duckdb.connect(
        str(client.app.state.settings.data_dir / "runs" / run / "run.duckdb"), read_only=True
    )
    barred = {
        r[0]
        for r in con.execute("SELECT cluster_id FROM service UNION SELECT cluster_id FROM victim").fetchall()
    }
    con.close()
    assert not {x["subject_ref"] for x in _leads(client, headers, run, type="ACTOR")} & barred


def test_filters_sort_and_search(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    everything = _leads(client, headers, run)
    assert {x["type"] for x in _leads(client, headers, run, type="TX")} <= {"TX"}
    assert all(x["p"] >= 0.5 for x in _leads(client, headers, run, min_p=0.5))
    assert [x["priority"] for x in everything] == sorted((x["priority"] for x in everything), reverse=True)
    by_p = _leads(client, headers, run, sort="confidence")
    assert [x["p"] for x in by_p] == sorted((x["p"] for x in by_p), reverse=True)
    first = everything[0]
    assert first["id"] in {x["id"] for x in _leads(client, headers, run, q=first["subject_ref"][:6])}
    assert (
        client.get(f"/api/v1/runs/{run}/leads", headers=headers, params={"q": "%_%' OR 1=1--"}).status_code
        == 200
    )


def test_triage_rules_and_audit(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    key = _leads(client, headers, run)[0]["lead_key"]
    ok = client.patch(f"/api/v1/leads/by-key/{key}/state", headers=headers, json={"status": "IN_REVIEW"})
    assert ok.status_code == 200 and ok.json()["status"] == "IN_REVIEW"
    bad = client.post(
        f"/api/v1/leads/by-key/{key}/feedback", headers=headers, json={"verdict": "dismiss", "run_id": run}
    )
    assert bad.status_code == 422  # a dismissal needs a reason
    fine = client.post(
        f"/api/v1/leads/by-key/{key}/feedback",
        headers=headers,
        json={"verdict": "dismiss", "reason_code": "benign_service", "run_id": run},
    )
    assert fine.status_code == 201
    assert _leads(client, headers, run, status="DISMISSED")[0]["lead_key"] == key
    assert (
        client.patch(
            f"/api/v1/leads/by-key/{key}/state", headers=headers, json={"status": "DISMISSED"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/leads/by-key/nope/state", headers=headers, json={"status": "IN_REVIEW"}
        ).status_code
        == 404
    )
    with client.app.state.db.read() as session:
        actions = session.scalars(select(AuditLog.action)).all()
        assert audit.verify(session).ok
    assert {"lead.status", "lead.feedback"} <= set(actions)


@pytest.mark.security
def test_only_leads_assign_and_other_roles_are_bounded(client: TestClient, analysed) -> None:
    headers, _, run, _ = analysed
    key = _leads(client, headers, run)[0]["lead_key"]
    analyst_user = add_user(client, "analyst")
    analyst = bearer(login(client, analyst_user))
    assert (
        client.patch(
            f"/api/v1/leads/by-key/{key}/state", headers=analyst, json={"assignee_id": analyst_user.id}
        ).status_code
        == 403
    )  # only lead analysts can assign
    assert (
        client.patch(
            f"/api/v1/leads/by-key/{key}/state", headers=headers, json={"assignee_id": analyst_user.id}
        ).status_code
        == 200
    )
    auditor = bearer(login(client, add_user(client, "auditor")))
    assert (
        client.patch(
            f"/api/v1/leads/by-key/{key}/state", headers=auditor, json={"status": "IN_REVIEW"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/leads/by-key/{key}/feedback",
            headers=auditor,
            json={"verdict": "confirm", "run_id": run},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/leads/by-key/{key}/state", headers=headers, json={"status": "IN_REVIEW", "extra": 1}
        ).status_code
        == 422
    )


def test_state_survives_a_rerun_and_diff_is_empty_for_same_data(client: TestClient, analysed) -> None:
    headers, dataset, run1, worker = analysed
    key = _leads(client, headers, run1)[0]["lead_key"]
    client.post(
        f"/api/v1/leads/by-key/{key}/feedback", headers=headers, json={"verdict": "confirm", "run_id": run1}
    )
    run2 = client.post("/api/v1/runs", headers=headers, json={"dataset_id": dataset}).json()
    _finish(client, headers, run2["job"]["id"], worker)
    rid = run2["run"]["id"]
    assert (
        client.get(f"/api/v1/runs/{rid}", headers=headers).json()["result_digest"]
        == client.get(f"/api/v1/runs/{run1}", headers=headers).json()["result_digest"]
    )
    carried = next(x for x in _leads(client, headers, rid) if x["lead_key"] == key)
    assert carried["state"]["status"] == "CONFIRMED"
    assert carried["state"]["changed_since_review"] is False  # nothing moved
    diff = client.get(f"/api/v1/runs/{rid}/diff", headers=headers).json()
    assert diff["against"] == run1 and (diff["new"], diff["gone"], diff["changed"]) == ([], [], [])


@pytest.mark.security
def test_demo_visitors_triage_privately(demo_client: TestClient) -> None:
    alice = bearer(demo_client.post("/api/v1/auth/demo").json())
    bob = bearer(demo_client.post("/api/v1/auth/demo").json())
    lead = _leads(demo_client, alice, "run_hero")[0]
    key = lead["lead_key"]
    assert (
        demo_client.post(
            f"/api/v1/leads/by-key/{key}/feedback",
            headers=alice,
            json={"verdict": "confirm", "run_id": "run_hero"},
        ).status_code
        == 201
    )
    assert _leads(demo_client, alice, "run_hero", status="CONFIRMED")[0]["lead_key"] == key
    assert (
        _leads(demo_client, bob, "run_hero", status="CONFIRMED") == []
    )  # bob sees his own, untouched, state
    assert _leads(demo_client, bob, "run_hero")[0]["state"] in (
        None,
        {"status": "NEW", "assignee_id": None, "changed_since_review": False},
    )
    lead_user = bearer(login(demo_client, add_user(demo_client, "lead")))
    assert _leads(demo_client, lead_user, "run_hero", status="CONFIRMED") == []  # shared state untouched
