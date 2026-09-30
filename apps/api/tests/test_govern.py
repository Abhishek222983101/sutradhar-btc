"""Govern: users, settings, models, audit — admin-only writes, everyone can read what they're allowed to."""

from __future__ import annotations

import pytest
from apitest import add_user, bearer, login
from fastapi.testclient import TestClient


def test_admin_manages_users_and_settings(client: TestClient) -> None:
    admin = bearer(login(client, add_user(client, "admin")))
    created = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": "new@example.org",
            "name": "New",
            "role": "analyst",
            "password": "correct-horse-battery",
        },
    )
    assert created.status_code == 201
    listed = client.get("/api/v1/users", headers=admin).json()["items"]
    assert any(u["email"] == "new@example.org" for u in listed)
    updated = client.patch(f"/api/v1/users/{created.json()['id']}", headers=admin, params={"role": "lead"})
    assert updated.json()["role"] == "lead"
    settings = client.get("/api/v1/settings", headers=admin).json()
    key = next(s["key"] for s in settings if isinstance(s["default"], float))
    put = client.put(f"/api/v1/settings/{key}", headers=admin, json=0.99)
    assert put.status_code == 200 and put.json()["changed"] is True


def test_models_and_audit_readable(client: TestClient) -> None:
    admin = bearer(login(client, add_user(client, "admin")))
    models = client.get("/api/v1/models", headers=admin).json()
    assert {m["name"] for m in models} >= {"lead_ranker", "origin", "change"}
    audit = client.get("/api/v1/audit", headers=admin).json()
    assert "items" in audit


@pytest.mark.security
def test_only_admin_can_write(client: TestClient) -> None:
    lead = bearer(login(client, add_user(client, "lead")))
    assert (
        client.post(
            "/api/v1/users",
            headers=lead,
            json={
                "email": "x@example.org",
                "name": "X",
                "role": "analyst",
                "password": "correct-horse-battery",
            },
        ).status_code
        == 403
    )
    assert client.put("/api/v1/settings/coinjoin.tau", headers=lead, json=0.5).status_code == 403
    assert client.get("/api/v1/users", headers=lead).status_code == 403


@pytest.mark.security
def test_weak_password_rejected(client: TestClient) -> None:
    admin = bearer(login(client, add_user(client, "admin")))
    assert (
        client.post(
            "/api/v1/users",
            headers=admin,
            json={"email": "weak@example.org", "name": "W", "role": "analyst", "password": "short"},
        ).status_code
        == 422
    )
