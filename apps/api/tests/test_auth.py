"""Sign-in, refresh rotation with reuse detection, logout, demo entry and token validation."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from apitest import JWT, PASSWORD, add_user, bearer, login
from fastapi.testclient import TestClient
from sqlalchemy import select

from sutradhar_api.auth import service
from sutradhar_api.auth.security import ALGORITHM, AUDIENCE, ISSUER
from sutradhar_api.auth.service import AuthError
from sutradhar_api.config import Settings
from sutradhar_api.models import AuditLog, AuthSession, RefreshToken


def test_login_and_me(client: TestClient) -> None:
    user = add_user(client, "analyst")
    tokens = login(client, user)
    assert tokens["token_type"] == "bearer"
    assert tokens["refresh_token"].startswith("rt_")
    me = client.get("/api/v1/me", headers=bearer(tokens)).json()
    assert (me["id"], me["role"]) == (user.id, "analyst")
    assert "dataset.upload" in me["permissions"]
    assert "admin.manage" not in me["permissions"]


@pytest.mark.security
def test_login_does_not_reveal_which_emails_exist(client: TestClient) -> None:
    user = add_user(client)
    wrong = client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope-nope-nope"})
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.org", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert wrong.headers["content-type"].startswith("application/problem+json")


@pytest.mark.security
def test_repeated_failures_lock_the_account_temporarily(client: TestClient) -> None:
    user = add_user(client)
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": user.email, "password": "bad-bad-bad"}
            ).status_code
            == 401
        )
    locked = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0


@pytest.mark.security
def test_login_rate_limited_per_client(client: TestClient) -> None:
    codes = [
        client.post(
            "/api/v1/auth/login", json={"email": f"x{i}@example.org", "password": "pw-pw-pw-pw"}
        ).status_code
        for i in range(12)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10:] == [429, 429]


def test_refresh_rotates(client: TestClient) -> None:
    first = login(client, add_user(client))
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    assert second.json()["refresh_token"] != first["refresh_token"]
    assert second.headers["cache-control"] == "no-store"
    third = client.post("/api/v1/auth/refresh", json={"refresh_token": second.json()["refresh_token"]})
    assert third.status_code == 200


@pytest.mark.security
def test_refresh_reuse_revokes_the_whole_session(client: TestClient) -> None:
    first = login(client, add_user(client))
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json()["type"].endswith("refresh_reuse")
    # the legitimate successor and every access token of the family are dead too
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code
        == 401
    )
    assert client.get("/api/v1/me", headers=bearer(second)).status_code == 401
    assert client.get("/api/v1/me", headers=bearer(first)).status_code == 401
    with client.app.state.db.read() as session:
        actions = session.scalars(select(AuditLog.action)).all()
    assert "auth.refresh_reuse" in actions


@pytest.mark.security
def test_concurrent_refresh_race_has_one_winner_and_revokes(client: TestClient) -> None:
    """Six parties present the same refresh token at once: exactly one rotation succeeds, and because the others
    prove the token was copied, the whole session is revoked (compare-and-set + family revocation)."""
    tokens = login(client, add_user(client))
    db, settings = client.app.state.db, client.app.state.settings
    results: list[str] = []
    barrier = threading.Barrier(6)

    def attempt() -> None:
        barrier.wait()
        with db.write() as session:
            try:
                service.refresh(session, settings, token=tokens["refresh_token"], client_ip=None)
                results.append("ok")
            except AuthError as exc:
                results.append(exc.code)

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("ok") == 1, results
    assert set(results) <= {"ok", "refresh_reuse", "session_ended"}, results
    with db.read() as session:
        active = session.scalars(select(RefreshToken).where(RefreshToken.status == "active")).all()
        family = session.scalars(select(AuthSession)).all()
    assert not active
    assert all(s.revoked_at is not None for s in family)


@pytest.mark.security
@pytest.mark.parametrize(
    "token",
    ["", "rt_", "rt_x.y", "garbage", "rt_" + "A" * 22 + "." + "B" * 43, "Bearer x" * 50],
)
def test_malformed_refresh_tokens_are_rejected(client: TestClient, token: str) -> None:
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code in (401, 422)


def test_logout_ends_the_session(client: TestClient) -> None:
    tokens = login(client, add_user(client))
    assert client.post("/api/v1/auth/logout", headers=bearer(tokens)).status_code == 204
    assert client.get("/api/v1/me", headers=bearer(tokens)).status_code == 401
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def _forge(claims_override: dict, *, key: str = JWT, algorithm: str = ALGORITHM) -> str:
    now = datetime.now(tz=UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "usr_x",
        "role": "admin",
        "sid": "sess_x",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    claims.update(claims_override)
    return jwt.encode(claims, key, algorithm=algorithm)


@pytest.mark.security
@pytest.mark.parametrize(
    "make_token",
    [
        lambda good: good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB"),  # bad signature
        lambda good: _forge({}, key="k" * 48),  # signed with another key
        lambda good: _forge({"aud": "someone-else"}),
        lambda good: _forge({"iss": "someone-else"}),
        lambda good: _forge({"exp": int(time.time()) - 3600}),
        lambda good: jwt.encode({"sub": "usr_x", "sid": "s", "role": "admin"}, None, algorithm="none"),
    ],
)
def test_forged_or_expired_tokens_are_rejected(client: TestClient, make_token: Callable[[str], str]) -> None:
    good = login(client, add_user(client))["access_token"]
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {make_token(good)}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.security
def test_role_comes_from_the_database_not_the_token(client: TestClient) -> None:
    """A validly signed token claiming admin for an analyst's session still acts as analyst."""
    user = add_user(client, "analyst")
    tokens = login(client, user)
    claims = jwt.decode(tokens["access_token"], JWT, algorithms=[ALGORITHM], audience=AUDIENCE)
    forged = _forge({"sub": claims["sub"], "sid": claims["sid"], "role": "admin"})
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {forged}"}).json()["role"] == "analyst"


def test_demo_login_only_in_demo_mode(client: TestClient, demo_client: TestClient) -> None:
    assert client.post("/api/v1/auth/demo").status_code == 404
    first = demo_client.post("/api/v1/auth/demo").json()
    second = demo_client.post("/api/v1/auth/demo").json()
    assert first["user"]["role"] == "demo"
    assert first["user"]["id"] != second["user"]["id"]  # each visitor gets their own account
    assert first["user"]["email"].endswith("@demo.invalid")


@pytest.mark.security
def test_demo_accounts_cannot_sign_in_with_a_password(demo_client: TestClient) -> None:
    visitor = demo_client.post("/api/v1/auth/demo").json()["user"]
    for guess in ("", "!", "demo", "x" * 40):
        response = demo_client.post(
            "/api/v1/auth/login", json={"email": visitor["email"], "password": guess or "x"}
        )
        assert response.status_code == 401


def test_non_dev_modes_require_a_real_secret(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(app_mode="demo", database_url=f"sqlite:///{tmp_path}/a.sqlite", jwt_secret="short")
    with pytest.raises(ValueError, match="OFFLINE_GUARD"):
        Settings(app_mode="airgap", jwt_secret="s" * 40, offline_guard="off")
    with pytest.raises(ValueError, match="CORS"):
        Settings(cors_origins="*")
    assert Settings(cors_origins="https://a.vercel.app, https://b.example.in").cors_origins == [
        "https://a.vercel.app",
        "https://b.example.in",
    ]
