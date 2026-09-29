"""Canonical serialisation and hashing — the same object always produces the same bytes and digest."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any

import orjson

GENESIS_HASH = "0" * 64
_CHUNK = 1 << 20


def _normalise(obj: Any) -> Any:
    """Make an object canonical: floats rounded to 6 decimals, Decimals as strings, containers recursed."""
    result: Any = obj
    if isinstance(obj, float):
        rounded = round(obj, 6)
        result = 0.0 if rounded == 0 else rounded  # collapse -0.0
    elif isinstance(obj, Decimal):
        result = format(obj, "f")
    elif isinstance(obj, dict):
        result = {str(key): _normalise(value) for key, value in obj.items()}
    elif isinstance(obj, list | tuple):
        result = [_normalise(value) for value in obj]
    elif isinstance(obj, set | frozenset):
        result = sorted(_normalise(value) for value in obj)
    elif hasattr(obj, "model_dump"):
        result = _normalise(obj.model_dump(mode="json"))
    return result


def canonical_json(obj: Any) -> bytes:
    """UTF-8 JSON with sorted keys and no insignificant whitespace."""
    return orjson.dumps(_normalise(obj), option=orjson.OPT_SORT_KEYS)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
