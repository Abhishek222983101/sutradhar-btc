"""Watchlists: lead-only management, strict validation, audited, and frozen into each run."""

from __future__ import annotations

import csv
import io

import duckdb
import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient
from sqlalchemy import select

from sutradhar_api.jobs.worker import Worker
from sutradhar_api.models import AuditLog, Run

A1 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"


@pytest.fixture
def lead(client: TestClient) -> dict[str, str]:
    return bearer(login(client, add_user(client, "lead")))


def _make(client: TestClient, headers: dict[str, str], name: str = "seeds", kind: str = "address") -> str:
    response = client.post("/api/v1/watchlists", headers=headers, json={"name": name, "kind": kind})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_lead_manages_and_everyone_can_read(client: TestClient, lead: dict[str, str]) -> None:
    wl = _make(client, lead)
    added = client.post(
        f"/api/v1/watchlists/{wl}/items",
        headers=lead,
        json={"value": A1, "category": "ransomware", "source": "victim report", "confidence": 0.95},
    )
    assert added.status_code == 201
    analyst = bearer(login(client, add_user(client, "analyst")))
    assert client.get("/api/v1/watchlists", headers=analyst).json()["items"][0]["name"] == "seeds"
    assert client.get(f"/api/v1/watchlists/{wl}/items", headers=analyst).json()["items"][0]["value"] == A1
    assert (
        client.delete(f"/api/v1/watchlists/{wl}/items/{added.json()['id']}", headers=lead).status_code == 204
    )
    with client.app.state.db.read() as session:
        actions = session.scalars(select(AuditLog.action)).all()
    assert {"watchlist.create", "watchlist.add", "watchlist.remove"} <= set(actions)


@pytest.mark.security
@pytest.mark.parametrize("role", ["analyst", "auditor"])
def test_only_lead_and_admin_can_change_watchlists(client: TestClient, role: str) -> None:
    headers = bearer(login(client, add_user(client, role)))
    assert client.post("/api/v1/watchlists", headers=headers, json={"name": "x-list"}).status_code == 403
    admin = bearer(login(client, add_user(client, "admin")))
    wl = _make(client, admin, "by-admin")
    assert (
        client.post(
            f"/api/v1/watchlists/{wl}/items", headers=headers, json={"value": A1, "source": "test source"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/watchlists/{wl}/import",
            headers=headers,
            files={"file": ("a.csv", b"value\n", "text/csv")},
        ).status_code
        == 403
    )


@pytest.mark.security
@pytest.mark.parametrize(
    "value",
    [
        '=HYPERLINK("http://evil")',
        "@SUM(1+1)",
        "<script>alert(1)</script>",
        "short",
        "a" * 200,
        "bc1q'; DROP TABLE users;--",
    ],
)
def test_hostile_values_are_rejected(client: TestClient, lead: dict[str, str], value: str) -> None:
    wl = _make(client, lead)
    assert (
        client.post(
            f"/api/v1/watchlists/{wl}/items", headers=lead, json={"value": value, "source": "test source"}
        ).status_code
        == 422
    )


@pytest.mark.security
def test_demo_visitors_cannot_change_watchlists(demo_client: TestClient) -> None:
    visitor = bearer(demo_client.post("/api/v1/auth/demo").json())
    assert demo_client.post("/api/v1/watchlists", headers=visitor, json={"name": "mine"}).status_code == 403
    assert demo_client.get("/api/v1/watchlists", headers=visitor).status_code == 200


def test_ip_watchlists_validate_ips(client: TestClient, lead: dict[str, str]) -> None:
    wl = _make(client, lead, "ips", "ip")
    ok = client.post(
        f"/api/v1/watchlists/{wl}/items",
        headers=lead,
        json={"value": "2001:DB8:0:0:0:0:0:7", "source": "test source"},
    )
    assert ok.json()["value"] == "2001:db8::7"
    assert (
        client.post(
            f"/api/v1/watchlists/{wl}/items",
            headers=lead,
            json={"value": "999.1.1.1", "source": "test source"},
        ).status_code
        == 422
    )


def test_csv_import_reports_bad_rows_and_keeps_good_ones(client: TestClient, lead: dict[str, str]) -> None:
    wl = _make(client, lead)
    body = f"address,category,source,confidence\n{A1},ransomware,report,0.9\n=1+1,scam,x,0.5\n{A1}x,bogus,x,0.5\nbc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq,theft,tip,2\n"
    result = client.post(
        f"/api/v1/watchlists/{wl}/import", headers=lead, files={"file": ("w.csv", body.encode(), "text/csv")}
    ).json()
    assert result["added"] == 1
    assert result["rejected_total"] == 3
    assert {r["line"] for r in result["rejected"]} == {3, 4, 5}
    again = client.post(
        f"/api/v1/watchlists/{wl}/import", headers=lead, files={"file": ("w.csv", body.encode(), "text/csv")}
    ).json()
    assert (again["added"], again["updated"]) == (0, 1)


@pytest.mark.security
def test_import_limits_and_bad_files(client: TestClient, lead: dict[str, str]) -> None:
    wl = _make(client, lead)
    url = f"/api/v1/watchlists/{wl}/import"
    assert (
        client.post(
            url, headers=lead, files={"file": ("w.csv", b"nothing,here\n1,2\n", "text/csv")}
        ).status_code
        == 400
    )
    assert (
        client.post(url, headers=lead, files={"file": ("w.csv", b"\xff\xfe\x00bad", "text/csv")}).status_code
        == 400
    )
    big = b"value\n" + b"x" * (5 * 1024 * 1024 + 10)
    assert client.post(url, headers=lead, files={"file": ("w.csv", big, "text/csv")}).status_code == 413
    assert (
        client.post(
            "/api/v1/watchlists/wl_nope/import",
            headers=lead,
            files={"file": ("w.csv", b"value\n", "text/csv")},
        ).status_code
        == 404
    )


def _run(client: TestClient, headers: dict[str, str], tiny_csv: bytes) -> tuple[str, str]:
    worker = Worker(client.app.state.settings, client.app.state.db)
    up = client.post(
        "/api/v1/datasets", headers=headers, files={"files": ("t.csv", tiny_csv, "text/csv")}
    ).json()
    while client.get(f"/api/v1/jobs/{up['job']['id']}", headers=headers).json()["status"] not in (
        "succeeded",
        "failed",
    ):
        worker.run_once()
    ds = up["dataset"]["id"]
    run = client.post("/api/v1/runs", headers=headers, json={"dataset_id": ds}).json()
    while client.get(f"/api/v1/jobs/{run['job']['id']}", headers=headers).json()["status"] not in (
        "succeeded",
        "failed",
    ):
        worker.run_once()
    return run["run"]["id"], ds


def test_watchlist_snapshot_frozen_per_run(client: TestClient, lead: dict[str, str], tiny_csv: bytes) -> None:
    row = next(csv.DictReader(io.StringIO(tiny_csv.decode())))
    seed = __import__("json").loads(row["input_addresses"])[0]
    wl = _make(client, lead)
    client.post(
        f"/api/v1/watchlists/{wl}/items",
        headers=lead,
        json={"value": seed, "category": "scam", "source": "test", "confidence": 0.9},
    )
    run_id, _ = _run(client, lead, tiny_csv)
    data_dir = client.app.state.settings.data_dir
    seeds_file = data_dir / "runs" / run_id / "seeds.csv"
    frozen = seeds_file.read_bytes()
    assert seed.encode() in frozen
    with client.app.state.db.read() as session:
        recorded = session.get(Run, run_id).refdata_versions["watchlist"]  # type: ignore[union-attr]
    assert recorded["items"] == 1 and len(recorded["sha256"]) == 64

    client.post(
        f"/api/v1/watchlists/{wl}/items", headers=lead, json={"value": A1, "source": "added later"}
    )  # after the run
    assert seeds_file.read_bytes() == frozen
    con = duckdb.connect(str(data_dir / "runs" / run_id / "run.duckdb"), read_only=True)
    assert con.execute("SELECT count(*) FROM taint WHERE is_seed AND address = ?", [seed]).fetchone()[0] == 1
    con.close()


def test_run_without_watchlist_has_no_seed_file(
    client: TestClient, lead: dict[str, str], tiny_csv: bytes
) -> None:
    run_id, _ = _run(client, lead, tiny_csv)
    assert not (client.app.state.settings.data_dir / "runs" / run_id / "seeds.csv").exists()
    with client.app.state.db.read() as session:
        assert session.get(Run, run_id).refdata_versions["watchlist"]["items"] == 0  # type: ignore[union-attr]
