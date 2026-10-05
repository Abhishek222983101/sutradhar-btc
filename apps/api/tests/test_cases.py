"""Cases, items, notes, exports (evidence pack, graphml, misp, i2csv) and verify — end to end."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient

from sutradhar_api.jobs.worker import Worker


def _analysed(client: TestClient, tiny_csv: bytes) -> tuple[dict[str, str], str]:
    headers = bearer(login(client, add_user(client, "lead")))
    worker = Worker(client.app.state.settings, client.app.state.db)
    up = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv, "text/csv")}
    ).json()
    while client.get(f"/api/v1/jobs/{up['job']['id']}", headers=headers).json()["status"] not in (
        "succeeded",
        "failed",
    ):
        worker.run_once()
    run = client.post("/api/v1/runs", headers=headers, json={"dataset_id": up["dataset"]["id"]}).json()
    while client.get(f"/api/v1/jobs/{run['job']['id']}", headers=headers).json()["status"] not in (
        "succeeded",
        "failed",
    ):
        worker.run_once()
    return headers, run["run"]["id"]


def test_case_lifecycle_and_evidence_pack(client: TestClient, tiny_csv: bytes) -> None:
    headers, run_id = _analysed(client, tiny_csv)
    leads = client.get(f"/api/v1/runs/{run_id}/leads", headers=headers, params={"limit": 5}).json()["items"]
    assert leads
    case = client.post("/api/v1/cases", headers=headers, json={"title": "Ransomware cluster"}).json()
    item = client.post(
        f"/api/v1/cases/{case['id']}/items",
        headers=headers,
        json={"item_kind": "lead", "ref": leads[0]["id"], "run_id": run_id},
    ).json()
    assert item["item_kind"] == "lead"
    client.post(f"/api/v1/cases/{case['id']}/notes", headers=headers, json={"body_md": "Looks solid."})
    notes = client.get(f"/api/v1/cases/{case['id']}/notes", headers=headers).json()
    assert notes and notes[0]["body_md"] == "Looks solid."
    export = client.post(
        f"/api/v1/cases/{case['id']}/exports", headers=headers, json={"kind": "evidence_pack"}
    ).json()
    assert export["status"] == "ready" and export["sha256"]
    dl = client.get(f"/api/v1/exports/{export['id']}/download", headers=headers)
    assert dl.status_code == 200
    with zipfile.ZipFile(BytesIO(dl.content)) as zf:
        assert "manifest.json" in zf.namelist()
    verify = client.post(
        "/api/v1/verify", headers=headers, files={"file": ("pack.zip", dl.content, "application/zip")}
    )
    assert verify.json()["ok"] is True and verify.json()["seal_valid"] is True
    with zipfile.ZipFile(BytesIO(dl.content)) as zf:
        files = {n: zf.read(n) for n in zf.namelist()}
    files["notes.md"] = b"tampered after export"
    forged = BytesIO()
    with zipfile.ZipFile(forged, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    bad = client.post(
        "/api/v1/verify", headers=headers, files={"file": ("pack.zip", forged.getvalue(), "application/zip")}
    ).json()
    assert bad["ok"] is False and bad["sha256_mismatches"] == ["notes.md"]
    assert (
        client.patch(f"/api/v1/cases/{case['id']}", headers=headers, params={"status": "closed"}).json()[
            "status"
        ]
        == "closed"
    )


@pytest.mark.parametrize("kind", ["graphml", "misp", "i2csv"])
def test_other_export_kinds(client: TestClient, tiny_csv: bytes, kind: str) -> None:
    headers, run_id = _analysed(client, tiny_csv)
    case = client.post("/api/v1/cases", headers=headers, json={"title": "case x"}).json()
    client.post(
        f"/api/v1/cases/{case['id']}/items",
        headers=headers,
        json={
            "item_kind": "address",
            "ref": "bc1qtestaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "run_id": run_id,
        },
    )
    export = client.post(f"/api/v1/cases/{case['id']}/exports", headers=headers, json={"kind": kind}).json()
    assert export["status"] == "ready"


@pytest.mark.security
def test_only_owner_or_lead_can_modify_case(client: TestClient, tiny_csv: bytes) -> None:
    headers, _run_id = _analysed(client, tiny_csv)
    case = client.post("/api/v1/cases", headers=headers, json={"title": "case x"}).json()
    other = bearer(login(client, add_user(client, "analyst")))
    assert (
        client.post(f"/api/v1/cases/{case['id']}/notes", headers=other, json={"body_md": "hi"}).status_code
        == 403
    )


def test_verify_rejects_garbage(client: TestClient, tiny_csv: bytes) -> None:
    headers, _ = _analysed(client, tiny_csv)
    verify = client.post(
        "/api/v1/verify", headers=headers, files={"file": ("x.zip", b"not a zip", "application/zip")}
    )
    assert verify.json()["ok"] is False
