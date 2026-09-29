"""Credential primitives: argon2id passwords, HS256 access tokens, opaque rotating refresh tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ISSUER = "sutradhar"
AUDIENCE = "sutradhar-api"
ALGORITHM = "HS256"
MIN_PASSWORD_LEN = 12
MAX_PASSWORD_LEN = 256

_hasher = PasswordHasher()  # argon2id, RFC 9106 low-memory profile (t=3, m=64 MiB, p=4)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    if len(password) > MAX_PASSWORD_LEN:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    """Verified against when the account does not exist, so response time does not reveal accounts."""
    return hash_password(secrets.token_urlsafe(32))


def unusable_password() -> str:
    """A hash no password verifies against (demo account: login only through /auth/demo)."""
    return "!" + secrets.token_hex(16)


def check_password_policy(password: str) -> None:
    if not MIN_PASSWORD_LEN <= len(password) <= MAX_PASSWORD_LEN:
        raise ValueError(f"password must be {MIN_PASSWORD_LEN} to {MAX_PASSWORD_LEN} characters")


def issue_access_token(
    *, key: str, user_id: str, role: str, session_id: str, now: datetime, ttl: timedelta
) -> tuple[str, datetime]:
    expires = now + ttl
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": user_id,
        "role": role,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(claims, key, algorithm=ALGORITHM), expires


def decode_access_token(token: str, key: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError for anything but a valid, unexpired token from this API."""
    return jwt.decode(
        token,
        key,
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=ISSUER,
        leeway=10,
        options={"require": ["exp", "iat", "nbf", "sub", "sid", "aud", "iss"]},
    )


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@dataclass(frozen=True, slots=True)
class RefreshSecret:
    selector: str
    secret: str

    @property
    def wire(self) -> str:
        return f"rt_{self.selector}.{self.secret}"

    @property
    def secret_hash(self) -> str:
        return hashlib.sha256(self.secret.encode()).hexdigest()


def new_refresh_secret() -> RefreshSecret:
    return RefreshSecret(selector=_b64(secrets.token_bytes(16)), secret=_b64(secrets.token_bytes(32)))


def parse_refresh_token(wire: str) -> RefreshSecret | None:
    if not wire.startswith("rt_") or len(wire) > 128:
        return None
    selector, sep, secret = wire[3:].partition(".")
    if not sep or len(selector) != 22 or len(secret) != 43:
        return None
    return RefreshSecret(selector=selector, secret=secret)


def secret_matches(stored_hash: str, presented: RefreshSecret) -> bool:
    return hmac.compare_digest(stored_hash, presented.secret_hash)
