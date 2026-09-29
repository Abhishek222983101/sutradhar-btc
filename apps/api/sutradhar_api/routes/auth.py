"""Session lifecycle: login, refresh, logout, demo entry, and who am I."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request, Response

from sutradhar_api.auth import service
from sutradhar_api.auth.permissions import Action, permissions_for
from sutradhar_api.auth.service import Principal, TokenPair
from sutradhar_api.deps import AppSettings, Signed, WriteDB, client_ip, public, rate_limit, require
from sutradhar_api.schemas import LoginIn, RefreshIn, TokenOut, UserOut

router = APIRouter(prefix="/api/v1", tags=["auth"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _user(principal_user: object) -> UserOut:
    out = UserOut.model_validate(principal_user)
    out.permissions = permissions_for(out.role)
    return out


def _tokens(pair: TokenPair, response: Response, settings: AppSettings) -> TokenOut:
    response.headers.update(NO_STORE)
    return TokenOut(
        access_token=pair.access_token,
        expires_in=settings.jwt_access_ttl_min * 60,
        refresh_token=pair.refresh_token,
        refresh_expires_at=pair.refresh_expires_at,
        user=_user(pair.user),
    )


@router.post(
    "/auth/login",
    dependencies=[public("auth.login"), rate_limit("login", limit=10, window_s=60)],
)
def login(
    body: LoginIn, request: Request, response: Response, db: WriteDB, settings: AppSettings
) -> TokenOut:
    pair = service.login(
        db,
        settings,
        email=body.email,
        password=body.password,
        client_ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return _tokens(pair, response, settings)


@router.post(
    "/auth/refresh",
    dependencies=[public("auth.refresh"), rate_limit("refresh", limit=60, window_s=60)],
)
def refresh(
    body: RefreshIn, request: Request, response: Response, db: WriteDB, settings: AppSettings
) -> TokenOut:
    pair = service.refresh(db, settings, token=body.refresh_token, client_ip=client_ip(request))
    return _tokens(pair, response, settings)


@router.post(
    "/auth/demo",
    dependencies=[public("auth.demo"), rate_limit("demo-login", limit=20, window_s=3600)],
)
def demo(request: Request, response: Response, db: WriteDB, settings: AppSettings) -> TokenOut:
    pair = service.demo_login(
        db, settings, client_ip=client_ip(request), user_agent=request.headers.get("user-agent")
    )
    return _tokens(pair, response, settings)


@router.post("/auth/logout", status_code=204)
def logout(principal: Annotated[Principal, require(Action.SESSION)], db: WriteDB) -> Response:
    service.logout(db, principal)
    return Response(status_code=204, headers=NO_STORE)


@router.get("/me")
def me(principal: Signed) -> UserOut:
    return _user(principal.user)
