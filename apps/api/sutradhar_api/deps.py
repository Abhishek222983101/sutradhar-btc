"""Request dependencies: settings, database sessions, the signed-in principal, and `require(action)`.

Every mutating route declares either `require(action)` or `public(action)`;
`test_every_mutating_endpoint_declares_permission` fails the build when one forgets.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from sutradhar_api.auth.permissions import Action, allowed
from sutradhar_api.auth.service import AuthError, Principal, authenticate
from sutradhar_api.config import Settings
from sutradhar_api.db import Database
from sutradhar_api.problems import Problem
from sutradhar_api.ratelimit import RateLimiter

_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login or /auth/demo")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.db


def write_session(db: Annotated[Database, Depends(get_database)]) -> Iterator[Session]:
    with db.write() as session:
        yield session


def read_session(db: Annotated[Database, Depends(get_database)]) -> Iterator[Session]:
    with db.read() as session:
        yield session


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Database, Depends(get_database)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthError("not_signed_in", "sign in to use this endpoint")
    with db.read() as session:
        return authenticate(session, settings, credentials.credentials)


def require(action: Action) -> Any:
    def checker(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if not allowed(principal.role, action):
            raise Problem(403, "forbidden", f"your role ({principal.role}) cannot perform {action}")
        return principal

    checker.__sutradhar_action__ = action  # type: ignore[attr-defined]
    return Depends(checker)


def public(action: str) -> Any:
    """Marks a deliberately unauthenticated mutating endpoint (sign-in flows)."""

    def marker() -> None:
        return None

    marker.__sutradhar_public__ = action  # type: ignore[attr-defined]
    return Depends(marker)


def rate_limit(bucket: str, *, limit: int, window_s: float, demo_only: bool = False) -> Any:
    def check(request: Request) -> None:
        if demo_only and not request.app.state.settings.is_demo:
            return
        limiter: RateLimiter = request.app.state.limiter
        retry = limiter.hit(bucket, client_ip(request) or "unknown", limit=limit, window_s=window_s)
        if retry is not None:
            raise Problem(
                429, "rate_limited", f"too many {bucket} requests", headers={"Retry-After": str(retry)}
            )

    return Depends(check)


def declared_action(dependency: Callable[..., Any]) -> str | None:
    return getattr(dependency, "__sutradhar_action__", None) or getattr(
        dependency, "__sutradhar_public__", None
    )


Signed = Annotated[Principal, Depends(current_principal)]
WriteDB = Annotated[Session, Depends(write_session)]
ReadDB = Annotated[Session, Depends(read_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
