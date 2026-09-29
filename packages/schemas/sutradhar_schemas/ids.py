"""Typed, time-sortable identifiers: `<prefix>_<ULID>` (e.g. `ds_01JC2…`). Mintable anywhere, no coordination."""

from __future__ import annotations

import os
import re
import time
from typing import Final

_CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PREFIXES: Final = frozenset(
    {"ds", "run", "job", "ld", "case", "exp", "usr", "mdl", "mp", "wl", "sess", "scn", "ev", "file"}
)
ID_RE: Final = re.compile(r"^(?P<prefix>[a-z]{2,4})_(?P<ulid>[0-9A-HJKMNP-TV-Z]{26})$")
# Ids chosen by people (e.g. `ds_demo`) are allowed but can never contain path or shell metacharacters.
SAFE_ID_RE: Final = re.compile(r"^(?P<prefix>[a-z]{2,4})_[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        chars.append(_CROCKFORD[rem])
    return "".join(reversed(chars))


def new_ulid(ms: int | None = None) -> str:
    ms = int(time.time() * 1000) if ms is None else ms
    rand = int.from_bytes(os.urandom(10), "big")
    return _encode(ms, 10) + _encode(rand, 16)


def new_id(prefix: str) -> str:
    if prefix not in PREFIXES:
        raise ValueError(f"unknown id prefix {prefix!r}")
    return f"{prefix}_{new_ulid()}"


def is_id(value: str, prefix: str | None = None) -> bool:
    match = ID_RE.fullmatch(value)
    return bool(match) and (prefix is None or match.group("prefix") == prefix)


def check_id(value: str, prefix: str) -> str:
    """Return `value` if it is a safe id with this prefix; ids become directory names, so this is a guard."""
    match = SAFE_ID_RE.fullmatch(value)
    if not match or match.group("prefix") != prefix:
        raise ValueError(
            f"invalid {prefix} id {value[:80]!r}: use {prefix}_ followed by letters, digits, '_' or '-'"
        )
    return value
