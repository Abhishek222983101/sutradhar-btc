"""API test fixtures. Every database test runs on SQLite; set SUTRADHAR_TEST_PG_URL to also run it on PostgreSQL
(CI does, with a service container)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from apitest import BACKENDS, JWT, PG_URL, _reset_pg, add_user, bearer, login
from fastapi.testclient import TestClient

from sutradhar_api import migrate
from sutradhar_api.app import create_app
from sutradhar_api.config import Settings
from sutradhar_api.db import Database


@pytest.fixture(params=BACKENDS)
def db_url(request: pytest.FixtureRequest, tmp_path: Path) -> str:
    if request.param == "postgresql":
        assert PG_URL is not None
        _reset_pg(PG_URL)
        return PG_URL
    return f"sqlite:///{tmp_path}/app.sqlite"


@pytest.fixture
def make_settings(db_url: str, tmp_path: Path) -> Callable[..., Settings]:
    def factory(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "app_mode": "dev",
            "database_url": db_url,
            "data_dir": tmp_path / "data",
            "jwt_secret": JWT,
            "offline_guard": "on",
            "embedded_worker": False,
        }
        values.update(overrides)
        return Settings(**values)

    return factory


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings()


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    migrate.upgrade(settings.database_url)
    db = Database(settings.database_url)
    yield db
    db.dispose()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def demo_client(make_settings: Callable[..., Settings]) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings(app_mode="demo", demo_upload_max_mb=1))) as test_client:
        yield test_client


@pytest.fixture
def as_role(client: TestClient) -> Callable[[str], dict[str, str]]:
    def headers(role: str) -> dict[str, str]:
        return bearer(login(client, add_user(client, role)))

    return headers


@pytest.fixture(scope="session")
def tiny_csv(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    from sutradhar_gen.config import PRESETS
    from sutradhar_gen.generate import generate

    out = tmp_path_factory.mktemp("world")
    generate(PRESETS["tiny"], 5, out)
    return (out / "data" / "traffic.csv").read_bytes()
