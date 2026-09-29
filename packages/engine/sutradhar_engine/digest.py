"""Content digests that do not depend on file formats: canonical JSON lines in primary-key order.

A table digest is SHA-256 over every row serialised as canonical JSON (sorted keys) followed by a newline,
in a stated order. Columns listed in `exclude` (e.g. provenance like run_id) are left out so that two runs
of the same inputs produce the same result digest (I4).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

import duckdb
import orjson

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(name: str) -> str:
    """Guard for SQL identifiers built from code constants — never from user input."""
    if not _IDENT.fullmatch(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


def table_digest(
    con: duckdb.DuckDBPyConnection,
    table: str,
    order_by: Iterable[str],
    *,
    exclude: Iterable[str] = (),
    batch_rows: int = 100_000,
) -> str:
    excluded = set(exclude)
    relation = con.table(ident(table))
    columns = [c for c in relation.columns if c not in excluded]
    if not columns:
        raise ValueError(f"{table}: no columns left to digest")
    digest = hashlib.sha256()
    digest.update(orjson.dumps(columns))
    ordered = relation.order(", ".join(f'"{ident(c)}"' for c in order_by))
    reader = ordered.project(", ".join(f'"{ident(c)}"' for c in columns)).to_arrow_reader(batch_rows)
    for batch in reader:
        for row in batch.to_pylist():
            digest.update(orjson.dumps(row, option=orjson.OPT_SORT_KEYS))
            digest.update(b"\n")
    return digest.hexdigest()


def combine(digests: dict[str, str]) -> str:
    """One digest over named digests, order-independent of dict insertion."""
    return hashlib.sha256(orjson.dumps(digests, option=orjson.OPT_SORT_KEYS)).hexdigest()
