"""Money is exact integer satoshis (I9); time is UTC microseconds (I10)."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sutradhar_schemas.units import (
    MAX_SUPPLY_SATS,
    SATS_PER_BTC,
    AmountError,
    micros_to_iso,
    sats_to_btc_str,
    to_sats,
    utc_micros,
)


@given(st.integers(min_value=0, max_value=MAX_SUPPLY_SATS))
def test_to_sats_decimal(sats: int) -> None:
    """Formatting satoshis as BTC and parsing back is lossless for every valid amount."""
    btc_text = sats_to_btc_str(sats)
    assert to_sats(btc_text, "btc") == sats
    assert to_sats(Decimal(btc_text), "btc") == sats
    assert to_sats(sats, "sat") == sats


@given(st.integers(min_value=0, max_value=10**12))
def test_float_btc_uses_shortest_repr(sats: int) -> None:
    value = float(sats_to_btc_str(sats))
    # Floats that round-trip through repr() convert exactly; others are rejected rather than rounded.
    with contextlib.suppress(AmountError):
        assert to_sats(value, "btc") == int(Decimal(repr(value)) * SATS_PER_BTC)


def test_common_float_amounts_convert_exactly() -> None:
    assert to_sats(0.1, "btc") == 10_000_000
    assert to_sats(0.3885, "btc") == 38_850_000
    assert to_sats(21_000_000, "btc") == MAX_SUPPLY_SATS


def test_no_float_money() -> None:
    """I9: conversions return int, never float."""
    for value, unit in ((0.42, "btc"), ("0.00000001", "btc"), (123, "sat"), (Decimal("1.5"), "btc")):
        assert type(to_sats(value, unit)) is int


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        (-1, "sat"),
        ("-0.1", "btc"),
        ("0.000000001", "btc"),  # finer than a satoshi
        ("1.5", "sat"),  # fractional satoshi
        (21_000_000.00000001, "btc"),
        (MAX_SUPPLY_SATS + 1, "sat"),
    ],
)
def test_invalid_amounts_rejected(value: object, unit: str) -> None:
    with pytest.raises(AmountError):
        to_sats(value, unit)  # type: ignore[arg-type]


@pytest.mark.security
@pytest.mark.parametrize(
    "hostile", ["NaN", "inf", "-inf", "1e999999", "9" * 100, "", "   ", "0x10", "1_000", True, None, [], {}]
)
def test_hostile_amount_inputs_rejected(hostile: object) -> None:
    with pytest.raises(AmountError):
        to_sats(hostile, "btc")


def test_timestamps_utc_micros() -> None:
    """I10: aware datetimes in any zone map to the same UTC microsecond instant."""
    ist = timezone(timedelta(hours=5, minutes=30))
    utc_dt = datetime(2026, 8, 21, 19, 44, 2, 113204, tzinfo=UTC)
    ist_dt = utc_dt.astimezone(ist)
    assert utc_micros(utc_dt) == utc_micros(ist_dt) == 1_787_341_442_113_204
    assert micros_to_iso(1_787_341_442_113_204) == "2026-08-21T19:44:02.113204Z"
    with pytest.raises(ValueError, match="naive"):
        utc_micros(datetime(2026, 1, 1))  # deliberately naive
