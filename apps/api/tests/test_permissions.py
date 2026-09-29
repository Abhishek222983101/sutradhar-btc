"""Authorisation is declared on every route (§2.4), lists are bounded (I12), and demo visitors are isolated."""

from __future__ import annotations

import typing
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from apitest import add_user, bearer, login
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from sutradhar_api.app import create_app
from sutradhar_api.auth.permissions import MATRIX, Action
from sutradhar_api.config import Settings
from sutradhar_api.deps import declared_action
from sutradhar_api.pagination import MAX_LIMIT, Page
from sutradhar_schemas.enums import Role

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _dependencies(dependant: Any) -> Iterator[Any]:
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependencies(dep)


def _routes() -> list[APIRoute]:
    app = create_app(Settings(embedded_worker=False, offline_guard="warn"))
    return [r for r in app.routes if isinstance(r, APIRoute)]


@pytest.mark.security
def test_every_mutating_endpoint_declares_permission() -> None:
    missing = [
        f"{sorted(r.methods)} {r.path}"
        for r in _routes()
        if r.methods & MUTATING and not any(declared_action(call) for call in _dependencies(r.dependant))
    ]
    assert not missing, f"endpoints without require()/public(): {missing}"


@pytest.mark.security
def test_every_data_endpoint_requires_sign_in() -> None:
    public_reads = {"/api/health", "/api/ready", "/api/v1/system/info", "/api/docs"}
    open_routes = [
        r.path
        for r in _routes()
        if r.path.startswith("/api/")
        and r.path not in public_reads
        and not any(
            declared_action(call) or call.__name__ == "current_principal"
            for call in _dependencies(r.dependant)
        )
    ]
    assert not open_routes, f"unauthenticated routes: {open_routes}"


def test_no_unpaginated_list_endpoints() -> None:
    for route in _routes():
        model = route.response_model
        origin = typing.get_origin(model)
        assert origin not in (list, tuple, set), f"{route.path} returns a bare list"
        if isinstance(model, type) and issubclass(model, Page):
            limit = next((p for p in route.dependant.query_params if p.name == "limit"), None)
            assert limit is not None, f"{route.path} has no limit"
            maximum = next(m.le for m in limit.field_info.metadata if hasattr(m, "le"))
            assert maximum <= MAX_LIMIT, route.path


def test_permission_matrix_matches_the_blueprint() -> None:
    assert MATRIX[Action.MODEL_PROMOTE] == {Role.ADMIN}
    assert Role.AUDITOR in MATRIX[Action.AUDIT_VERIFY]
    assert Role.AUDITOR not in MATRIX[Action.DATASET_UPLOAD]
    assert Role.DEMO not in MATRIX[Action.AUDIT_VIEW]
    assert all(MATRIX[a] for a in Action)


@pytest.mark.security
@pytest.mark.parametrize(
    ("role", "method", "path", "expected"),
    [
        ("auditor", "post", "/api/v1/runs", 403),
        ("analyst", "get", "/api/v1/audit/verify", 403),
        ("auditor", "get", "/api/v1/audit/verify", 200),
        ("lead", "get", "/api/v1/audit/verify", 200),
    ],
)
def test_role_matrix_is_enforced(
    client: TestClient,
    as_role: Callable[[str], dict[str, str]],
    role: str,
    method: str,
    path: str,
    expected: int,
) -> None:
    kwargs: dict[str, Any] = {"json": {"dataset_id": "ds_missing"}} if method == "post" else {}
    response = getattr(client, method)(path, headers=as_role(role), **kwargs)
    assert response.status_code == expected, response.text


@pytest.mark.security
def test_auditor_cannot_upload(client: TestClient, as_role: Callable[[str], dict[str, str]]) -> None:
    response = client.post(
        "/api/v1/datasets", headers=as_role("auditor"), files={"files": ("a.csv", b"x\n", "text/csv")}
    )
    assert response.status_code == 403


@pytest.mark.security
def test_demo_visitors_cannot_see_each_other(demo_client: TestClient, tiny_csv: bytes) -> None:
    alice = bearer(demo_client.post("/api/v1/auth/demo").json())
    bob = bearer(demo_client.post("/api/v1/auth/demo").json())
    upload = demo_client.post(
        "/api/v1/datasets", headers=alice, files={"files": ("t.csv", tiny_csv[:4000], "text/csv")}
    )
    assert upload.status_code == 202, upload.text
    dataset_id, job_id = upload.json()["dataset"]["id"], upload.json()["job"]["id"]
    assert demo_client.get(f"/api/v1/datasets/{dataset_id}", headers=alice).status_code == 200
    assert demo_client.get(f"/api/v1/datasets/{dataset_id}", headers=bob).status_code == 404
    assert demo_client.get(f"/api/v1/jobs/{job_id}", headers=bob).status_code == 404
    assert [d["id"] for d in demo_client.get("/api/v1/datasets", headers=bob).json()["items"]] == ["ds_hero"]
    assert demo_client.post(f"/api/v1/jobs/{job_id}/cancel", headers=bob).status_code == 404


@pytest.mark.security
def test_unauthenticated_requests_get_a_problem_document(client: TestClient) -> None:
    response = client.get("/api/v1/datasets")
    assert response.status_code == 401
    body = response.json()
    assert body["type"] == "urn:sutradhar:problem:not_signed_in"
    assert body["instance"].startswith("urn:sutradhar:request:")
    assert response.headers["www-authenticate"] == "Bearer"


def test_admin_sees_other_users_jobs(client: TestClient, tiny_csv: bytes) -> None:
    analyst = bearer(login(client, add_user(client, "analyst")))
    admin = bearer(login(client, add_user(client, "admin")))
    job_id = client.post(
        "/api/v1/datasets", headers=analyst, files={"files": ("t.csv", tiny_csv[:4000], "text/csv")}
    ).json()["job"]["id"]
    other_analyst = bearer(login(client, add_user(client, "analyst")))
    assert client.get(f"/api/v1/jobs/{job_id}", headers=admin).status_code == 200
    assert client.get(f"/api/v1/jobs/{job_id}", headers=other_analyst).status_code == 404
