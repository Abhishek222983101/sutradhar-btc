"""Pure ASGI middleware (safe for streaming responses): request ids, security headers, body-size limits and a
per-client rate limit. Pure ASGI rather than BaseHTTPMiddleware so SSE streams are never buffered."""

from __future__ import annotations

import logging
import re
import secrets
import time
from collections.abc import Callable
from typing import Any

from starlette.exceptions import HTTPException as StarletteHTTPException

from sutradhar_api.ratelimit import RateLimiter

log = logging.getLogger("sutradhar.access")
Scope = dict[str, Any]
ASGIApp = Callable[..., Any]
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


def _problem_bytes(status: int, code: str, detail: str) -> bytes:
    title = {413: "Too large", 429: "Too many requests"}.get(status, "Error")
    return (
        f'{{"type":"urn:sutradhar:problem:{code}","title":"{title}","status":{status},"detail":"{detail}"}}'
    ).encode()


async def _send_problem(
    send: Any, status: int, code: str, detail: str, extra: list[tuple[bytes, bytes]]
) -> None:
    body = _problem_bytes(status, code, detail)
    headers = [
        (b"content-type", b"application/problem+json"),
        (b"content-length", str(len(body)).encode()),
        *extra,
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class SecurityHeaders:
    def __init__(self, app: ASGIApp, *, hsts: bool, docs_csp: Callable[[], str]) -> None:
        self.app, self.hsts, self.docs_csp = app, hsts, docs_csp

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID.match(incoming) else secrets.token_hex(8)
        scope.setdefault("state", {})["request_id"] = request_id
        path: str = scope.get("path", "")
        started = time.perf_counter()
        status_holder = {"status": 0}

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                csp = self.docs_csp() if path == "/api/docs" else API_CSP
                extra = [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"content-security-policy", csp.encode()),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ]
                if path.startswith("/api/v1/") and b"cache-control" not in present:
                    extra.append((b"cache-control", b"no-store"))
                if self.hsts:
                    extra.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = headers + [h for h in extra if h[0] not in present]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if path != "/api/health":
                log.info(
                    "%s %s %s %.1fms rid=%s",
                    scope.get("method"),
                    path,
                    status_holder["status"],
                    (time.perf_counter() - started) * 1000,
                    request_id,
                )


class BodySizeLimit:
    """Refuse bodies over the limit while they arrive, not after they have filled the disk."""

    def __init__(self, app: ASGIApp, *, default_bytes: int, upload_bytes: Callable[[], int]) -> None:
        self.app, self.default_bytes, self.upload_bytes = app, default_bytes, upload_bytes

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/api/v1/datasets":
            limit = self.upload_bytes() + 1024 * 1024
        elif path.endswith("/import"):
            limit = 6 * 1024 * 1024  # watchlist CSV imports (the route enforces its own 5 MB cap)
        else:
            limit = self.default_bytes
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > limit):
            await _send_problem(send, 413, "too_large", f"request body limit is {limit} bytes", [])
            return
        received = 0
        response_started = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge()
            return message

        async def tracking_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not response_started:
                await _send_problem(send, 413, "too_large", f"request body limit is {limit} bytes", [])


class _TooLarge(StarletteHTTPException):
    """An HTTPException so FastAPI's body parser re-raises it as-is (413), instead of wrapping it as a 400."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail="the request body is larger than allowed")


class RateLimit:
    def __init__(self, app: ASGIApp, *, limiter: RateLimiter, per_minute: Callable[[], int]) -> None:
        self.app, self.limiter, self.per_minute = app, limiter, per_minute

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") in ("/api/health", "/api/ready"):
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        key = client[0] if client else "unknown"
        retry = self.limiter.hit("general", key, limit=self.per_minute(), window_s=60)
        if retry is not None:
            await _send_problem(
                send, 429, "rate_limited", "slow down", [(b"retry-after", str(retry).encode())]
            )
            return
        await self.app(scope, receive, send)
