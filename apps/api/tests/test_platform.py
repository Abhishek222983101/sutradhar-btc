"""HTTP hardening: security headers, self-hosted docs (I11), body limits, CORS, problem documents and schema drift."""

from __future__ import annotations

import re

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from sutradhar_api import migrate
from sutradhar_api.app import create_app
from sutradhar_api.config import Settings
from sutradhar_api.models import Base


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    ready = client.get("/api/ready").json()
    assert ready["status"] == "ready"
    assert ready["checks"] == {"database": True, "schema": True, "data_dir": True}


@pytest.mark.security
def test_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/system/info")
    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["content-security-policy"].startswith("default-src 'none'")
    assert headers["cache-control"] == "no-store"
    assert re.fullmatch(r"[0-9a-f]{16}", headers["x-request-id"])
    assert "server" not in headers


@pytest.mark.security
def test_request_ids_are_sanitised(client: TestClient) -> None:
    echoed = client.get("/api/health", headers={"X-Request-ID": "abcDEF12-3456"}).headers["x-request-id"]
    assert echoed == "abcDEF12-3456"
    hostile = client.get("/api/health", headers={"X-Request-ID": "<script>alert(1)</script>"}).headers[
        "x-request-id"
    ]
    assert re.fullmatch(r"[0-9a-f]{16}", hostile)


@pytest.mark.security
def test_docs_load_nothing_from_the_internet(client: TestClient) -> None:
    page = client.get("/api/docs")
    assert page.status_code == 200
    html = page.text
    assert not re.findall(r"(?:src|href)=\"https?://", html), "docs must reference only local assets"
    assert '"validatorUrl": null' in html
    csp = page.headers["content-security-policy"]
    assert "connect-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    for asset in re.findall(r"(?:src|href)=\"(/api/static/[^\"]+)\"", html):
        assert client.get(asset).status_code == 200
    spec = client.get("/api/openapi.json").json()
    assert spec["info"]["title"] == "Sutradhar API"


@pytest.mark.security
def test_json_bodies_are_limited(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=b'{"email":"' + b"a" * (2 * 1024 * 1024) + b'","password":"x"}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


@pytest.mark.security
def test_validation_errors_do_not_echo_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "x", "password": "p", "extra": "<b>secret</b>"}
    )
    assert response.status_code == 422
    assert "<b>secret</b>" not in response.text
    assert response.json()["type"] == "urn:sutradhar:problem:validation"


@pytest.mark.security
def test_unknown_routes_are_problems_not_html(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.security
def test_cors_allows_only_configured_origins(make_settings) -> None:  # type: ignore[no-untyped-def]
    settings = make_settings(cors_origins="https://sutradhar.vercel.app")
    with TestClient(create_app(settings)) as cors_client:
        allowed = cors_client.options(
            "/api/v1/me",
            headers={"Origin": "https://sutradhar.vercel.app", "Access-Control-Request-Method": "GET"},
        )
        assert allowed.headers["access-control-allow-origin"] == "https://sutradhar.vercel.app"
        assert "access-control-allow-credentials" not in allowed.headers
        denied = cors_client.options(
            "/api/v1/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
        )
        assert "access-control-allow-origin" not in denied.headers


@pytest.mark.security
def test_general_rate_limit(make_settings) -> None:  # type: ignore[no-untyped-def]
    with TestClient(create_app(make_settings(rate_limit_per_min=5))) as limited:
        codes = [limited.get("/api/v1/system/info").status_code for _ in range(7)]
        assert codes == [200] * 5 + [429] * 2
        assert limited.get("/api/health").status_code == 200  # liveness is never limited


def test_models_match_migrations(settings: Settings) -> None:
    migrate.upgrade(settings.database_url)
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        diff = compare_metadata(
            MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata
        )
    engine.dispose()
    assert diff == []


def test_downgrade_is_refused() -> None:
    from importlib import import_module

    module = import_module("sutradhar_api.migrations.versions.0001_initial")
    with pytest.raises(NotImplementedError):
        module.downgrade()
