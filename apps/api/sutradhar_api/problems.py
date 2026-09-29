"""RFC 9457 problem details for every error. `type` is a URN, never a URL, so no client is tempted to fetch it.

Validation errors list where and why, but never echo the submitted value back. Unexpected errors return a
bare 500 with the request id; the traceback goes to the log only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sutradhar_api.auth.service import AuthError

log = logging.getLogger("sutradhar.api")
MEDIA_TYPE = "application/problem+json"
_TITLES = {
    400: "Bad request",
    401: "Not signed in",
    403: "Not allowed",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    413: "Too large",
    415: "Unsupported file type",
    422: "Invalid input",
    429: "Too many requests",
    500: "Internal error",
    503: "Unavailable",
}


class Problem(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str | None = None,
        *,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or code)
        self.status, self.code, self.detail, self.errors, self.headers = status, code, detail, errors, headers


def problem_response(
    request: Request,
    status: int,
    code: str,
    detail: str | None = None,
    *,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:sutradhar:problem:{code}",
        "title": _TITLES.get(status, "Error"),
        "status": status,
        "detail": detail,
        "instance": f"urn:sutradhar:request:{getattr(request.state, 'request_id', 'unknown')}",
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=MEDIA_TYPE, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem) -> JSONResponse:
        return problem_response(
            request, exc.status, exc.code, exc.detail, errors=exc.errors, headers=exc.headers
        )

    @app.exception_handler(AuthError)
    async def _auth(request: Request, exc: AuthError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else {}
        if exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        return problem_response(request, exc.status, exc.code, str(exc), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "loc": [str(p) for p in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": err.get("type"),
            }
            for err in exc.errors()[:50]
        ]
        return problem_response(request, 422, "validation", "the request is not valid", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        detail = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else None
        return problem_response(request, exc.status_code, code, detail, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return problem_response(
            request, 500, "internal", "something went wrong; the request id identifies it"
        )
