"""Uploads: formats, size and row caps, hostile filenames, idempotency, and nothing left behind on failure."""

from __future__ import annotations

from pathlib import Path

import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from sutradhar_api.models import AuditLog, Dataset, DatasetFile
from sutradhar_api.routes.datasets import safe_filename


@pytest.fixture
def analyst(client: TestClient) -> dict[str, str]:
    return bearer(login(client, add_user(client, "analyst")))


def _uploads(client: TestClient) -> list[Path]:
    root = client.app.state.settings.data_dir / "uploads"
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


def test_upload_creates_dataset_job_and_audit_entry(
    client: TestClient, analyst: dict[str, str], tiny_csv: bytes
) -> None:
    response = client.post(
        "/api/v1/datasets", headers=analyst, files={"files": ("traffic.csv", tiny_csv, "text/csv")}
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["dataset"]["status"] == "uploaded"
    assert body["job"]["kind"] == "ingest"
    assert body["job"]["status"] == "queued"
    with client.app.state.db.read() as session:
        files = session.scalars(select(DatasetFile)).all()
        actions = session.scalars(select(AuditLog.action)).all()
    assert [f.filename for f in files] == ["traffic.csv"]
    assert len(files[0].sha256) == 64
    assert "dataset.upload" in actions


@pytest.mark.security
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.csv", "passwd.csv"),
        ("..\\..\\windows\\evil.csv", "evil.csv"),
        ("/abs/path/x.csv", "x.csv"),
        ("we ird;$(id)`.csv", "we_ird_id_.csv"),
        ("....csv", "csv"),
        ("", "upload"),
        (None, "upload"),
        ("a" * 300 + ".csv", "a" * 80 + ".csv"),
    ],
)
def test_filenames_are_sanitised(raw: str | None, expected: str) -> None:
    assert safe_filename(raw) == expected


@pytest.mark.security
def test_traversal_filename_stays_inside_the_upload_folder(
    client: TestClient, analyst: dict[str, str], tiny_csv: bytes
) -> None:
    response = client.post(
        "/api/v1/datasets",
        headers=analyst,
        files={"files": ("../../../escape.csv", tiny_csv[:2000], "text/csv")},
    )
    assert response.status_code == 202
    data_dir = client.app.state.settings.data_dir.resolve()
    for path in _uploads(client):
        assert path.resolve().is_relative_to(data_dir / "uploads")
    assert not (data_dir.parent / "escape.csv").exists()


@pytest.mark.security
@pytest.mark.parametrize("name", ["x.exe", "x.csv.php", "x.html", "x", "x.svg"])
def test_other_file_types_are_refused(client: TestClient, analyst: dict[str, str], name: str) -> None:
    response = client.post(
        "/api/v1/datasets", headers=analyst, files={"files": (name, b"a,b\n1,2\n", "text/csv")}
    )
    assert response.status_code == 415
    assert _uploads(client) == []


def test_empty_file_is_refused(client: TestClient, analyst: dict[str, str]) -> None:
    response = client.post("/api/v1/datasets", headers=analyst, files={"files": ("e.csv", b"", "text/csv")})
    assert response.status_code == 400
    assert _uploads(client) == []


def test_too_many_files(client: TestClient, analyst: dict[str, str]) -> None:
    files = [("files", (f"f{i}.csv", b"a\n", "text/csv")) for i in range(11)]
    assert client.post("/api/v1/datasets", headers=analyst, files=files).status_code == 400


@pytest.mark.security
def test_demo_upload_cap_is_enforced_while_streaming(demo_client: TestClient) -> None:
    visitor = bearer(demo_client.post("/api/v1/auth/demo").json())
    big = b"x" * (2 * 1024 * 1024)  # the demo cap in tests is 1 MB
    response = demo_client.post(
        "/api/v1/datasets", headers=visitor, files={"files": ("big.csv", big, "text/csv")}
    )
    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/problem+json")
    assert _uploads(demo_client) == []
    with demo_client.app.state.db.read() as session:
        assert session.scalar(select(func.count()).select_from(Dataset)) == 0


@pytest.mark.security
def test_demo_row_cap(make_settings, tiny_csv: bytes) -> None:  # type: ignore[no-untyped-def]
    from sutradhar_api.app import create_app

    with TestClient(create_app(make_settings(app_mode="demo", demo_upload_max_rows=100))) as demo:
        visitor = bearer(demo.post("/api/v1/auth/demo").json())
        response = demo.post(
            "/api/v1/datasets", headers=visitor, files={"files": ("t.csv", tiny_csv, "text/csv")}
        )
        assert response.status_code == 413
        assert response.json()["type"].endswith("too_many_rows")


@pytest.mark.security
def test_demo_uploads_expire(demo_client: TestClient, tiny_csv: bytes) -> None:
    visitor = bearer(demo_client.post("/api/v1/auth/demo").json())
    body = demo_client.post(
        "/api/v1/datasets", headers=visitor, files={"files": ("t.csv", tiny_csv[:3000], "text/csv")}
    )
    assert body.json()["dataset"]["expires_at"] is not None


def test_idempotency_key_returns_the_same_job(
    client: TestClient, analyst: dict[str, str], tiny_csv: bytes
) -> None:
    headers = {**analyst, "Idempotency-Key": "upload-1"}
    first = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv[:3000], "text/csv")}
    )
    second = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv[:3000], "text/csv")}
    )
    assert first.status_code == second.status_code == 202
    assert first.json()["job"]["id"] == second.json()["job"]["id"]
    assert first.json()["dataset"]["id"] == second.json()["dataset"]["id"]
    assert len(_uploads(client)) == 1


@pytest.mark.security
def test_idempotency_keys_are_per_user(client: TestClient, tiny_csv: bytes) -> None:
    a = bearer(login(client, add_user(client)))
    b = bearer(login(client, add_user(client)))
    files = {"files": ("t.csv", tiny_csv[:3000], "text/csv")}
    first = client.post("/api/v1/datasets", headers={**a, "Idempotency-Key": "same"}, files=files)
    second = client.post("/api/v1/datasets", headers={**b, "Idempotency-Key": "same"}, files=files)
    assert first.json()["job"]["id"] != second.json()["job"]["id"]


def test_list_is_paginated(client: TestClient, analyst: dict[str, str], tiny_csv: bytes) -> None:
    for i in range(5):
        client.post(
            "/api/v1/datasets", headers=analyst, files={"files": (f"t{i}.csv", tiny_csv[:2000], "text/csv")}
        )
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/v1/datasets", headers=analyst, params=params).json()
        seen += [d["id"] for d in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 5


@pytest.mark.security
@pytest.mark.parametrize("cursor", ["%%%", "bm90LWpzb24", "WzEsMiwzXQ", "WyJ4IiwxXQ", "W251bGwsbnVsbF0"])
def test_hostile_cursors_are_rejected(client: TestClient, analyst: dict[str, str], cursor: str) -> None:
    response = client.get("/api/v1/datasets", headers=analyst, params={"cursor": cursor})
    assert response.status_code == 400
    assert client.get("/api/v1/datasets", headers=analyst, params={"limit": 501}).status_code == 422
