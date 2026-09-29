"""I03/I04 — normalise mapped rows into typed observations and per-transaction content, rejecting bad rows.

Observations (one per row) keep only what varies per row: time, network endpoints, txid, provenance.
Transaction content (addresses, amounts, fee) is parsed once per distinct (txid, content) variant — exact
satoshis via Decimal (I9) — which is both faster and the basis for conflict detection (V10).
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from sutradhar_engine.ingest.readers import ROW_NO
from sutradhar_schemas.contract import ADDRESS_RE
from sutradhar_schemas.profile import MappingProfile, TimestampSpec
from sutradhar_schemas.scripts import infer_script_type
from sutradhar_schemas.units import GENESIS_US, AmountError, to_sats, utc_micros

TXID_PATTERN = r"^[0-9a-f]{64}$"
_EPOCH_RE = re.compile(r"^\d{9,17}(\.\d+)?$")
_ISO_FAST = "%Y-%m-%dT%H:%M:%S%.fZ"
_MAX_FUTURE_US = 86_400 * 1_000_000


@dataclass(slots=True)
class Rejects:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self, file_id: str, row_no: int, rule: str, *, field_name: str | None, value: object, message: str
    ) -> None:
        text = None if value is None else str(value)[:200]
        self.rows.append(
            {
                "file_id": file_id,
                "row_no": row_no,
                "rule": rule,
                "field": field_name,
                "value": text,
                "message": message,
            }
        )


def _now_us() -> int:
    return utc_micros(datetime.now(tz=UTC))


def parse_timestamps(values: pl.Series, spec: TimestampSpec) -> pl.Series:
    """Text → UTC microseconds (Int64); null where unparseable. Epoch units auto-detected by magnitude."""
    text = values.cast(pl.String)
    fast = text.str.strptime(pl.Datetime("us", "UTC"), _ISO_FAST, strict=False).dt.epoch("us")
    missing = fast.is_null() & text.is_not_null()
    if not missing.any():
        return fast
    zone = UTC if spec.tz.upper() == "UTC" else ZoneInfo(spec.tz)
    cache: dict[str, int | None] = {}

    def slow(raw: str) -> int | None:
        if raw in cache:
            return cache[raw]
        result: int | None = None
        stripped = raw.strip()
        try:
            if _EPOCH_RE.fullmatch(stripped) and spec.unit in ("auto", "s", "ms", "us"):
                number = float(stripped)
                unit = spec.unit
                if unit == "auto":
                    unit = "s" if number < 1e11 else "ms" if number < 1e14 else "us"
                result = round(number * {"s": 1_000_000, "ms": 1_000, "us": 1}[unit])
            elif spec.unit in ("auto", "iso"):
                parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=zone)
                result = utc_micros(parsed)
        except (ValueError, OverflowError):
            result = None
        cache[raw] = result
        return result

    slow_values = [
        slow(v) if m else f for v, m, f in zip(text.to_list(), missing.to_list(), fast.to_list(), strict=True)
    ]
    return pl.Series(values.name, slow_values, dtype=pl.Int64)


def canonical_ips(values: pl.Series) -> tuple[pl.Series, set[str]]:
    """Canonical IP text; returns (series with invalid → null, set of invalid raw values)."""
    mapping: dict[str, str | None] = {}
    invalid: set[str] = set()
    for raw in values.drop_nulls().unique().to_list():
        try:
            mapping[raw] = str(ipaddress.ip_address(raw.strip()))
        except ValueError:
            mapping[raw] = None
            invalid.add(raw)
    return values.replace_strict(mapping, default=None, return_dtype=pl.String), invalid


def normalise_observations(
    mapped: pl.DataFrame, file_id: str, profile: MappingProfile, rejects: Rejects
) -> pl.DataFrame:
    """Typed observation rows. Rows failing V01 to V04 are reported and dropped."""
    ts = parse_timestamps(mapped["timestamp"], profile.timestamp)
    src_ip, bad_src = canonical_ips(mapped["src_ip"])
    dst_ip, bad_dst = canonical_ips(mapped["dst_ip"])
    frame = mapped.select(
        pl.col(ROW_NO).alias("row_no"),
        pl.col("txid").str.to_lowercase().alias("txid"),
        pl.col("src_port").cast(pl.Int64, strict=False).alias("src_port"),
        pl.col("dst_port").cast(pl.Int64, strict=False).alias("dst_port"),
        pl.col("geo_country").str.to_uppercase().alias("geo_src"),
        pl.col("asn").cast(pl.Int64, strict=False).alias("asn_src"),
        pl.col("src_ip").alias("src_raw"),
        pl.col("dst_ip").alias("dst_raw"),
        pl.col("src_port").alias("src_port_raw"),
        pl.col("dst_port").alias("dst_port_raw"),
        pl.col("timestamp").alias("ts_raw"),
    ).with_columns(ts_us=ts, src_ip=src_ip, dst_ip=dst_ip)

    now = _now_us()
    net_present = pl.any_horizontal(
        pl.col(c).is_not_null() for c in ("src_raw", "dst_raw", "src_port_raw", "dst_port_raw")
    )
    net_complete = pl.all_horizontal(
        pl.col(c).is_not_null() for c in ("src_ip", "dst_ip", "src_port", "dst_port")
    )
    port_ok = pl.col("src_port").is_between(0, 65535) & pl.col("dst_port").is_between(0, 65535)
    checks = frame.with_columns(
        v01=~pl.col("txid").str.contains(TXID_PATTERN).fill_null(value=False),
        v04=pl.col("ts_us").is_null()
        | (pl.col("ts_us") < GENESIS_US)
        | (pl.col("ts_us") > now + _MAX_FUTURE_US),
        v02=net_present
        & (
            pl.col("src_raw").is_in(list(bad_src | bad_dst))
            | pl.col("dst_raw").is_in(list(bad_src | bad_dst))
            | ~net_complete
        ),
        v03=net_present & net_complete & ~port_ok,
    )
    for rule, column, field_name, message in (
        ("V01", "txid", "txid", "txid must be 64 hexadecimal characters"),
        ("V04", "ts_raw", "timestamp", "timestamp missing, unparseable or outside [2009-01-03, now + 1 day]"),
        ("V02", "src_raw", "src_ip/dst_ip", "network fields incomplete or not a valid IPv4/IPv6 address"),
        ("V03", "src_port_raw", "src_port/dst_port", "port outside 0 to 65535"),
    ):
        bad = checks.filter(pl.col(rule.lower()))
        for row_no, value in zip(bad["row_no"].to_list(), bad[column].to_list(), strict=True):
            rejects.add(file_id, row_no, rule, field_name=field_name, value=value, message=message)
    good = checks.filter(~(pl.col("v01") | pl.col("v04") | pl.col("v02") | pl.col("v03")))
    return good.select(
        "ts_us",
        pl.when(net_complete).then(pl.col("src_ip")).alias("src_ip"),
        pl.when(net_complete).then(pl.col("src_port").cast(pl.Int32)).alias("src_port"),
        pl.when(net_complete).then(pl.col("dst_ip")).alias("dst_ip"),
        pl.when(net_complete).then(pl.col("dst_port").cast(pl.Int32)).alias("dst_port"),
        "txid",
        pl.lit(file_id).alias("file_id"),
        pl.col("row_no").cast(pl.Int64),
        pl.col("geo_src"),
        pl.col("asn_src"),
    )


@dataclass(frozen=True, slots=True)
class TxContent:
    txid: str
    in_addresses: tuple[str, ...]
    in_sats: tuple[int, ...]
    out_addresses: tuple[str, ...]
    out_sats: tuple[int, ...]
    fee_sats: int
    fee_src: str

    def key(self) -> tuple[Any, ...]:
        return (self.in_addresses, self.in_sats, self.out_addresses, self.out_sats)


class ContentError(ValueError):
    def __init__(self, rule: str, field_name: str, message: str) -> None:
        super().__init__(message)
        self.rule, self.field_name = rule, field_name


def parse_content(txid: str, row: dict[str, Any], unit: str) -> TxContent:
    """One transaction's addresses and amounts → exact satoshis. Raises ContentError with a rule id."""
    in_addr = tuple(row["input_addresses"] or ())
    out_addr = tuple(row["output_addresses"] or ())
    in_raw = tuple(row["input_amounts"] or ())
    out_raw = tuple(row["output_amounts"] or ())
    if len(in_addr) != len(in_raw):
        raise ContentError("V05", "input_amounts", "input addresses and amounts differ in length")
    if len(out_addr) != len(out_raw):
        raise ContentError("V05", "output_amounts", "output addresses and amounts differ in length")
    if not out_addr:
        raise ContentError("V07", "output_addresses", "transaction has no outputs")
    for address in in_addr + out_addr:
        if not ADDRESS_RE.fullmatch(address):
            raise ContentError("V12", "addresses", f"implausible address {address[:24]!r}")
    try:
        in_sats = tuple(to_sats(v, unit) for v in in_raw)  # type: ignore[arg-type]
        out_sats = tuple(to_sats(v, unit) for v in out_raw)  # type: ignore[arg-type]
    except AmountError as exc:
        raise ContentError("V06", "amounts", f"invalid amount: {exc}") from exc
    if in_sats and sum(out_sats) > sum(in_sats):
        raise ContentError("V08", "amounts", "outputs exceed inputs")
    computed = 0 if not in_sats else sum(in_sats) - sum(out_sats)
    fee_src = "computed"
    fee_raw = row.get("fee")
    if fee_raw not in (None, ""):
        try:
            provided = to_sats(fee_raw, unit)  # type: ignore[arg-type]
        except AmountError as exc:
            raise ContentError("V06", "fee", f"invalid fee: {exc}") from exc
        if in_sats and abs(provided - computed) <= 1:
            fee_src = "provided"
    return TxContent(txid, in_addr, in_sats, out_addr, out_sats, computed, fee_src)


def script_types(addresses: tuple[str, ...]) -> list[str]:
    return [str(infer_script_type(a)) for a in addresses]
