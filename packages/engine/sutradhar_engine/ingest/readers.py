"""I01 — streaming readers. Every value is read as text; typing happens in normalisation (no float money).

P0.4 ships CSV/TSV. P2.1 adds JSON arrays, NDJSON, XML and compressed inputs behind the same interface.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import polars as pl

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
    else:
        raise ReaderError(f"{profile.format} is not supported yet")


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
