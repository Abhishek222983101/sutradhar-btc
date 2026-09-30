"""I01 — streaming readers. Every value is read as text; typing happens in normalisation (no float money).

P0.4 ships CSV/TSV. P2.1 adds JSON arrays, NDJSON, XML and compressed inputs behind the same interface.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import iterparse as safe_iterparse

from sutradhar_schemas.enums import FileFormat
from sutradhar_schemas.profile import MappingProfile

ROW_NO = "__row_no"


@dataclass(frozen=True, slots=True)
class SourceFile:
    file_id: str
    path: Path
    sha256: str
    bytes: int


class ReaderError(ValueError):
    """The file cannot be read with the given profile (wrong format, broken encoding, ...)."""


def read_batches(
    source: SourceFile, profile: MappingProfile, batch_rows: int = 100_000
) -> Iterator[pl.DataFrame]:
    """Yield string-typed frames with a 1-based source line number column (`__row_no`)."""
    if profile.format in (FileFormat.CSV, FileFormat.TSV):
        yield from _csv_batches(source, profile, batch_rows)
    elif profile.format in (FileFormat.JSON, FileFormat.NDJSON):
        yield from _frames(_json_records(source, profile), source, batch_rows)
    elif profile.format == FileFormat.XML:
        yield from _frames(_xml_records(source, profile), source, batch_rows)
    else:
        raise ReaderError(f"{profile.format} is not supported")


MAX_RECORD_BYTES = 1 << 20


def _text(value: object) -> str | None:
    """Every value becomes text; nested lists become JSON text so the same array mapping serves all formats."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return json.dumps(
            [v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v) for v in value]
        )
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


def _json_records(source: SourceFile, profile: MappingProfile) -> Iterator[tuple[int, dict[str, str | None]]]:
    try:
        if profile.format == FileFormat.NDJSON:
            with source.path.open(encoding="utf-8") as handle:
                for no, line in enumerate(handle, start=1):
                    if line.strip():
                        yield no, _record(json.loads(line))
        else:
            data = json.loads(source.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ReaderError(f"{source.path.name}: expected a JSON array of records")
            for no, item in enumerate(data, start=1):
                yield no, _record(item)
    except (ValueError, OSError) as exc:  # includes JSONDecodeError and UnicodeDecodeError
        raise ReaderError(f"cannot read {source.path.name}: {exc}") from exc


def _record(item: object) -> dict[str, str | None]:
    if not isinstance(item, dict):
        raise ValueError("each record must be a JSON object")
    if len(json.dumps(item)) > MAX_RECORD_BYTES:
        raise ValueError("record too large")
    return {str(k): _text(v) for k, v in item.items()}


def _xml_records(source: SourceFile, profile: MappingProfile) -> Iterator[tuple[int, dict[str, str | None]]]:
    """Streams `<record>` elements. DTDs, entities and external references are refused (I15)."""
    tag = profile.xml.record_tag
    no = 0
    try:
        for _event, element in safe_iterparse(
            str(source.path), events=("end",), forbid_dtd=True, forbid_entities=True, forbid_external=True
        ):
            if element.tag != tag:
                continue
            no += 1
            record: dict[str, str | None] = {}
            for child in element:
                kids = list(child)
                record[child.tag] = (
                    _text([(k.text or "").strip() for k in kids])
                    if kids
                    else (child.text or "").strip() or None
                )
            yield no, record
            element.clear()
    except (DefusedXmlException, ParseError, OSError) as exc:
        raise ReaderError(f"cannot read {source.path.name}: {type(exc).__name__}: {str(exc)[:120]}") from exc


def _frames(
    records: Iterator[tuple[int, dict[str, str | None]]], source: SourceFile, batch_rows: int
) -> Iterator[pl.DataFrame]:
    rows: list[dict[str, str | None]] = []
    numbers: list[int] = []
    for no, record in records:
        rows.append(record)
        numbers.append(no)
        if len(rows) >= batch_rows:
            yield _frame(rows, numbers)
            rows, numbers = [], []
    if rows:
        yield _frame(rows, numbers)


def _frame(rows: list[dict[str, str | None]], numbers: list[int]) -> pl.DataFrame:
    columns = sorted({k for r in rows for k in r})
    data = {c: [r.get(c) for r in rows] for c in columns}
    return pl.DataFrame(data, schema=dict.fromkeys(columns, pl.String)).with_columns(
        pl.Series(ROW_NO, numbers, dtype=pl.Int64)
    )


def _csv_batches(source: SourceFile, profile: MappingProfile, batch_rows: int) -> Iterator[pl.DataFrame]:
    opts = profile.csv
    separator = "\t" if profile.format == FileFormat.TSV else opts.delimiter
    first_line = 2 if opts.header else 1
    try:
        lazy = pl.scan_csv(
            source.path,
            separator=separator,
            quote_char=opts.quote,
            has_header=opts.header,
            infer_schema=False,  # every value stays text until normalisation (no float money)
            encoding="utf8" if opts.encoding == "utf-8" else "utf8-lossy",
            row_index_name=ROW_NO,
            row_index_offset=first_line,
            truncate_ragged_lines=True,
            raise_if_empty=False,
        )
        for frame in lazy.collect_batches(chunk_size=batch_rows, maintain_order=True):
            if frame.height:
                yield frame.with_columns(pl.col(ROW_NO).cast(pl.Int64))
    except (pl.exceptions.ComputeError, pl.exceptions.NoDataError, OSError) as exc:
        raise ReaderError(f"cannot read {source.path.name}: {exc}") from exc
