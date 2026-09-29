"""Helpers shared by the API tests (a uniquely named module, so it never collides with another conftest)."""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from sutradhar_api.auth.security import hash_password
from sutradhar_api.db import Database, utcnow
from sutradhar_api.models import User
from sutradhar_schemas.ids import new_id

PG_URL = os.environ.get("SUTRADHAR_TEST_PG_URL")
PASSWORD = "correct-horse-battery-staple"
JWT = "t" * 48
BACKENDS = [
    "sqlite",
    pytest.param("postgresql", marks=pytest.mark.skipif(not PG_URL, reason="no test Postgres")),
]


def _reset_pg(url: str) -> None:
    engine = create_engine(url)
    with engine.begin() as con:
        con.execute(text("DROP SCHEMA public CASCADE"))
        con.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def add_user(client_or_db: TestClient | Database, role: str = "analyst", email: str | None = None) -> User:
    db = client_or_db.app.state.db if isinstance(client_or_db, TestClient) else client_or_db
    with db.write() as session:
        user = User(
            id=new_id("usr"),
            email=email or f"{role}-{new_id('usr')[-6:].lower()}@example.org",
            name=role.title(),
            role=role,
            password_hash=hash_password(PASSWORD),
            is_active=True,
            created_at=utcnow(),
        )
        session.add(user)
        session.commit()
        return user


def login(client: TestClient, user: User) -> dict[str, Any]:
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
