"""Sessions: login, refresh rotation with reuse detection, logout, demo entry, and request authentication.

One login is one session (a refresh-token family). Each refresh consumes the presented token with a
compare-and-set and issues its successor; presenting a consumed token again revokes the whole family
(RFC 9700 §4.14.2), which also kills its access tokens because every request checks the session.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from sutradhar_api import audit
from sutradhar_api.auth.security import (
    decode_access_token,
    dummy_hash,
    issue_access_token,
    new_refresh_secret,
    parse_refresh_token,
    secret_matches,
    unusable_password,
    verify_password,
)
from sutradhar_api.config import Settings
from sutradhar_api.db import utcnow
from sutradhar_api.models import AuditLog, AuthSession, RefreshToken, User
from sutradhar_schemas.enums import Role
from sutradhar_schemas.ids import new_id

FAILED_WINDOW = timedelta(minutes=15)
MAX_FAILURES = 5


class AuthError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 401, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.code, self.status, self.retry_after = code, status, retry_after


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    user: User
    session_id: str


@dataclass(frozen=True)
class Principal:
    user: User
    session_id: str

    @property
    def role(self) -> str:
        return self.user.role


def _issue(db: Session, settings: Settings, user: User, family: AuthSession, now: datetime) -> TokenPair:
    secret = new_refresh_secret()
    db.add(
        RefreshToken(id=secret.selector, session_id=family.id, secret_hash=secret.secret_hash, created_at=now)
    )
    access, access_exp = issue_access_token(
        key=settings.signing_key,
        user_id=user.id,
        role=user.role,
        session_id=family.id,
        now=now,
        ttl=timedelta(minutes=settings.jwt_access_ttl_min),
    )
    return TokenPair(access, access_exp, secret.wire, family.expires_at, user, family.id)


def _open_session(
    db: Session, settings: Settings, user: User, *, client_ip: str | None, user_agent: str | None
) -> TokenPair:
    now = utcnow()
    family = AuthSession(
        id=new_id("sess"),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(hours=settings.jwt_refresh_ttl_h),
        client_ip=client_ip,
        user_agent=(user_agent or "")[:256] or None,
    )
    db.add(family)
    user.last_login_at = now
    db.flush()
    return _issue(db, settings, user, family, now)


def _recent_failures(db: Session, user_id: str) -> int:
    since = utcnow() - FAILED_WINDOW
    return int(
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "auth.failed", AuditLog.actor_id == user_id, AuditLog.ts > since)
        )
        or 0
    )


def login(
    db: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    client_ip: str | None,
    user_agent: str | None,
) -> TokenPair:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.is_active and _recent_failures(db, user.id) >= MAX_FAILURES:
        raise AuthError(
            "too_many_attempts",
            "too many failed sign-ins; try again later",
            status=429,
            retry_after=int(FAILED_WINDOW.total_seconds()),
        )
    usable = user is not None and user.is_active and user.role != Role.DEMO
    target_hash = user.password_hash if user is not None and usable else dummy_hash()
    password_ok = verify_password(target_hash, password)  # always runs: timing does not reveal accounts
    if user is None or not usable or not password_ok:
        audit.append(
            db,
            actor_id=user.id if user else None,
            actor_role=user.role if user else "anonymous",
            action="auth.failed",
            target_kind="user",
            target_ref=user.id if user else "unknown",
            payload={"email_sha256": hashlib.sha256(email.encode()).hexdigest()[:16], "ip": client_ip},
        )
        db.commit()
        raise AuthError("invalid_credentials", "email or password is incorrect")
    pair = _open_session(db, settings, user, client_ip=client_ip, user_agent=user_agent)
    audit.append(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="auth.login",
        target_kind="session",
        target_ref=pair.session_id,
        payload={"ip": client_ip},
    )
    db.commit()
    return pair


def demo_login(
    db: Session, settings: Settings, *, client_ip: str | None, user_agent: str | None
) -> TokenPair:
    """Each visitor gets a fresh demo account, so uploads and runs are theirs alone (blueprint §2.3)."""
    if not settings.is_demo:
        raise AuthError("not_found", "demo sessions exist only in demo mode", status=404)
    now = utcnow()
    user_id = new_id("usr")
    user = User(
        id=user_id,
        email=f"visitor-{user_id[-10:].lower()}@demo.invalid",
        name="Demo visitor",
        role=Role.DEMO,
        password_hash=unusable_password(),
        is_active=True,
        created_at=now,
    )
    db.add(user)
    db.flush()
    pair = _open_session(db, settings, user, client_ip=client_ip, user_agent=user_agent)
    audit.append(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="auth.login",
        target_kind="session",
        target_ref=pair.session_id,
        payload={"demo": True, "ip": client_ip},
    )
    db.commit()
    return pair


def _revoke_family(db: Session, family: AuthSession, reason: str) -> None:
    now = utcnow()
    if family.revoked_at is None:
        family.revoked_at, family.revoked_reason = now, reason
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.session_id == family.id, RefreshToken.status == "active")
        .values(status="revoked")
    )


def _reuse_detected(db: Session, family_id: str, client_ip: str | None) -> AuthError:
    db.rollback()
    family = db.get(AuthSession, family_id)
    if family is not None:
        _revoke_family(db, family, "refresh_reuse")
        audit.append(
            db,
            actor_id=family.user_id,
            actor_role="system",
            action="auth.refresh_reuse",
            target_kind="session",
            target_ref=family.id,
            payload={"ip": client_ip},
        )
        db.commit()
    return AuthError("refresh_reuse", "this refresh token was already used; the session has been ended")


def refresh(db: Session, settings: Settings, *, token: str, client_ip: str | None) -> TokenPair:
    presented = parse_refresh_token(token)
    row = db.get(RefreshToken, presented.selector) if presented else None
    if presented is None or row is None or not secret_matches(row.secret_hash, presented):
        raise AuthError("invalid_refresh", "refresh token is not valid")
    family = db.get(AuthSession, row.session_id)
    now = utcnow()
    if family is None or family.revoked_at is not None:
        raise AuthError("session_ended", "this session has ended; sign in again")
    if family.expires_at <= now:
        raise AuthError("session_expired", "this session has expired; sign in again")
    if row.status != "active":
        raise _reuse_detected(db, family.id, client_ip)
    user = db.get(User, family.user_id)
    if user is None or not user.is_active:
        raise AuthError("session_ended", "this account is disabled")
    consumed = db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.status == "active")
        .values(status="rotated", rotated_at=now)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:  # lost a race: someone else presented the same token at the same moment
        raise _reuse_detected(db, family.id, client_ip)
    pair = _issue(db, settings, user, family, now)
    db.commit()
    return pair


def logout(db: Session, principal: Principal) -> None:
    family = db.get(AuthSession, principal.session_id)
    if family is not None:
        _revoke_family(db, family, "logout")
        audit.append(
            db,
            actor_id=principal.user.id,
            actor_role=principal.role,
            action="auth.logout",
            target_kind="session",
            target_ref=family.id,
        )
    db.commit()


def authenticate(db: Session, settings: Settings, token: str) -> Principal:
    """Bearer access token -> the signed-in user. The session is checked on every request, so logout and
    reuse detection take effect immediately; the role is read from the database, not the token."""
    try:
        claims = decode_access_token(token, settings.signing_key)
    except jwt.PyJWTError as exc:
        raise AuthError("invalid_token", "access token is missing, expired or not valid") from exc
    found = db.execute(
        select(User, AuthSession)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(AuthSession.id == claims["sid"], User.id == claims["sub"])
    ).first()
    if found is None:
        raise AuthError("invalid_token", "access token is not valid")
    user, family = found
    if family.revoked_at is not None or family.expires_at <= utcnow() or not user.is_active:
        raise AuthError("session_ended", "this session has ended; sign in again")
    return Principal(user=user, session_id=family.id)
