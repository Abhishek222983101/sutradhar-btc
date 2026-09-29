"""Money and time units. Money is integer satoshis (I9); time is UTC microseconds (I10).

Every conversion into the canonical units goes through this module so there is exactly one place where
rounding, range checks and malformed input are handled.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, Literal

from pydantic import Field

SATS_PER_BTC: Final = 100_000_000
MAX_SUPPLY_BTC: Final = 21_000_000
MAX_SUPPLY_SATS: Final = MAX_SUPPLY_BTC * SATS_PER_BTC
MAX_AMOUNT_TEXT_LEN: Final = 40  # longer numeric strings are rejected before parsing (DoS guard)
MAX_MAGNITUDE: Final = 16  # no valid amount (in BTC or sats) has more than 17 integer digits
_NUMBER_RE: Final = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?$")

# The Bitcoin genesis block (2009-01-03) — no real observation can be earlier.
GENESIS_US: Final = 1_230_940_800_000_000

Sats = Annotated[int, Field(ge=0, le=MAX_SUPPLY_SATS, description="Amount in satoshis (integer).")]
TsUs = Annotated[int, Field(ge=0, description="UTC timestamp in microseconds since the Unix epoch.")]

AmountUnit = Literal["btc", "sat"]


class AmountError(ValueError):
    """Raised when a value cannot be converted into a valid satoshi amount."""


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, bool):  # bool is an int subclass; never a valid amount
        raise AmountError("boolean is not an amount")
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, float):
        # repr() gives the shortest round-trip form: 0.1 -> '0.1', never 0.1000000000000000055…
        dec = Decimal(repr(value))
    elif isinstance(value, str):
        text = value.strip()
        if not text or len(text) > MAX_AMOUNT_TEXT_LEN:
            raise AmountError("amount text is empty or too long")
        if not _NUMBER_RE.match(text):
            raise AmountError(f"not a plain decimal number: {text!r}")
        try:
            dec = Decimal(text)
        except InvalidOperation as exc:
            raise AmountError(f"not a number: {text!r}") from exc
    else:
        raise AmountError(f"unsupported amount type: {type(value).__name__}")
    if not dec.is_finite():
        raise AmountError("amount must be finite")
    if dec != 0 and dec.adjusted() > MAX_MAGNITUDE:
        # Checked before any arithmetic so hostile exponents cannot force huge integer conversions.
        raise AmountError("amount is too large")
    return dec


def to_sats(value: object, unit: AmountUnit) -> int:
    """Convert a BTC or satoshi amount to integer satoshis, exactly.

    BTC values may carry at most 8 decimal places; satoshi values must be integral. Negative amounts and
    amounts above the 21 M BTC supply are rejected.
    """
    dec = _as_decimal(value)
    if dec < 0:
        raise AmountError("amount must not be negative")
    if unit == "btc":
        scaled = dec * SATS_PER_BTC
    elif unit == "sat":
        scaled = dec
    else:  # pragma: no cover - guarded by the Literal type
        raise AmountError(f"unknown unit {unit!r}")
    if scaled != scaled.to_integral_value():
        raise AmountError("amount has more precision than one satoshi")
    sats = int(scaled)
    if sats > MAX_SUPPLY_SATS:
        raise AmountError("amount exceeds the 21 million BTC supply")
    return sats


def sats_to_btc_str(sats: int) -> str:
    """Format satoshis as a BTC string with exactly 8 decimals (display only, never re-parsed as float)."""
    if sats < 0:
        raise AmountError("amount must not be negative")
    whole, frac = divmod(sats, SATS_PER_BTC)
    return f"{whole}.{frac:08d}"


def utc_micros(dt: datetime) -> int:
    """Convert an aware datetime to UTC microseconds. Naive datetimes are rejected (ambiguous)."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("naive datetime: attach a timezone before converting")
    delta = dt.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def micros_to_datetime(ts_us: int) -> datetime:
    """UTC datetime for a microsecond timestamp."""
    seconds, micros = divmod(ts_us, 1_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=micros)


def micros_to_iso(ts_us: int) -> str:
    """ISO-8601 UTC string with microseconds and a trailing Z."""
    return micros_to_datetime(ts_us).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
