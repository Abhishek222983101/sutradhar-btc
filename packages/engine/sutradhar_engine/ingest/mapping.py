"""I02 — apply a mapping profile: source columns → logical input fields (all still text).

Array fields become List[String] columns; scalar fields stay String. Missing optional fields become nulls;
a missing required field is an error that names the column.
"""

from __future__ import annotations

import polars as pl

from sutradhar_engine.ingest.readers import ROW_NO
from sutradhar_schemas.contract import ALL_INPUT_FIELDS
from sutradhar_schemas.profile import FieldMap, MappingProfile


class MappingError(ValueError):
    """The source layout does not match the profile."""


def _array_expr(column: str, spec: FieldMap) -> pl.Expr:
    array = spec.array
    if array is None:
        raise MappingError(f"{spec.field!r} is not declared as an array")
    col = pl.col(column)
    if array.encoding == "json":
        # JSON arrays of strings or numbers → strip brackets, split, unquote. Numbers keep their exact text.
        inner = col.str.strip_chars().str.strip_prefix("[").str.strip_suffix("]")
        parts = inner.str.split(",").list.eval(pl.element().str.strip_chars().str.strip_chars('"'))
        return (
            pl.when(inner.str.strip_chars() == "").then(pl.lit([], dtype=pl.List(pl.String))).otherwise(parts)
        )
    if array.encoding == "delimited":
        parts = col.str.split(array.sep).list.eval(pl.element().str.strip_chars())
        return (
            pl.when(col.str.strip_chars() == "").then(pl.lit([], dtype=pl.List(pl.String))).otherwise(parts)
        )
    raise MappingError(f"array encoding {array.encoding!r} is not supported yet")


def _transform(expr: pl.Expr, transform: str | None) -> pl.Expr:
    match transform:
        case None:
            return expr
        case "lower":
            return expr.str.to_lowercase()
        case "upper":
            return expr.str.to_uppercase()
        case "strip":
            return expr.str.strip_chars()
        case "strip_as_prefix":
            return expr.str.strip_chars().str.replace(r"^(?i:AS)", "")
    raise MappingError(f"unknown transform {transform!r}")


def apply_profile(frame: pl.DataFrame, profile: MappingProfile) -> pl.DataFrame:
    """Return a frame with one column per logical input field plus the row number."""
    exprs: list[pl.Expr] = [pl.col(ROW_NO)]
    ts_source = profile.timestamp.field
    if ts_source not in frame.columns:
        raise MappingError(f"timestamp column {ts_source!r} not found; columns are {frame.columns[:20]}")
    exprs.append(pl.col(ts_source).str.strip_chars().alias("timestamp"))
    for target in ALL_INPUT_FIELDS:
        if target == "timestamp":
            continue
        spec = profile.fields.get(target)
        if spec is None:
            exprs.append(
                pl.lit(
                    None,
                    dtype=pl.List(pl.String)
                    if target.endswith(("addresses", "amounts", "types", "prevouts"))
                    else pl.String,
                ).alias(target)
            )
            continue
        if spec.field not in frame.columns:
            if spec.optional:
                dtype = pl.List(pl.String) if spec.array else pl.String
                exprs.append(pl.lit(None, dtype=dtype).alias(target))
                continue
            raise MappingError(f"column {spec.field!r} (for {target}) not found")
        expr = (
            _array_expr(spec.field, spec)
            if spec.array
            else _transform(pl.col(spec.field).str.strip_chars(), spec.transform)
        )
        if spec.array and spec.transform:
            expr = expr.list.eval(_transform(pl.element(), spec.transform))
        exprs.append(expr.alias(target))
    return frame.select(exprs)
