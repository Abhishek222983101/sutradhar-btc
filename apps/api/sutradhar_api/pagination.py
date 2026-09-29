"""I12 — no list endpoint returns an unbounded list. Keyset pagination with opaque cursors."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel

from sutradhar_api.problems import Problem

MAX_LIMIT = 500
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT, description=f"Page size (at most {MAX_LIMIT}).")]
Cursor = Annotated[str | None, Query(max_length=512, description="Opaque cursor from `next_cursor`.")]


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(values: list[Any]) -> str:
    raw = json.dumps(values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str | None, types: tuple[type, ...]) -> list[Any] | None:
    """The cursor must decode to a list whose items have exactly these types, or the request is rejected."""
    if cursor is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        values = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise Problem(400, "bad_cursor", "the cursor is not valid") from exc
    if not isinstance(values, list) or len(values) != len(types):
        raise Problem(400, "bad_cursor", "the cursor is not valid")
    for value, expected in zip(values, types, strict=True):
        ok = isinstance(value, expected) and not (expected is not bool and isinstance(value, bool))
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            ok = True
        if not ok:
            raise Problem(400, "bad_cursor", "the cursor is not valid")
    return values


def cursor_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Problem(400, "bad_cursor", "the cursor is not valid") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
