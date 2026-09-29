"""Data contract v1: valid records round-trip; every inconsistency is rejected with a clear reason."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from sutradhar_schemas import CanonicalRecord, ScriptType

TXID = "9c1e5b7d2a4f6e8c0b1d3f5a7c9e2b4d6f8a0c2e4b6d8f0a1c3e5b7d9f2a4c6e"
P2WPKH = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
P2TR = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
P2PKH = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts_us": 1_787_341_442_113_204,
        "txid": TXID.upper(),
        "src_ip": "198.51.100.23",
        "src_port": 51544,
        "dst_ip": "2001:DB8:0:0:0:0:0:7",
        "dst_port": 8333,
        "input_addresses": (P2WPKH,),
        "input_sats": (42_000_000,),
        "output_addresses": (P2TR, P2PKH),
        "output_sats": (3_100_000, 38_850_000),
        "fee_sats": 50_000,
        "output_script_types": (ScriptType.P2TR, ScriptType.P2PKH),
        "geo_country_src": "in",
        "asn_src": 55836,
    }
    base.update(overrides)
    return base


def test_contract_roundtrip() -> None:
    record = CanonicalRecord(**_record())
    assert record.txid == TXID  # lower-cased
    assert record.dst_ip == "2001:db8::7"  # canonical IPv6
    assert record.geo_country_src == "IN"
    assert record.computed_fee_sats == 50_000
    assert CanonicalRecord.model_validate_json(record.model_dump_json()) == record


def test_coinbase_has_no_inputs() -> None:
    record = CanonicalRecord(**_record(input_addresses=(), input_sats=(), fee_sats=None))
    assert record.is_coinbase
    assert record.computed_fee_sats == 0


def test_chain_only_record_without_network_fields() -> None:
    record = CanonicalRecord(**_record(src_ip=None, src_port=None, dst_ip=None, dst_port=None))
    assert record.src_ip is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"txid": "abc"}, "64 hex"),
        ({"src_ip": "999.1.1.1"}, "IPv4 or IPv6"),
        ({"input_sats": (1, 2)}, "differ in length"),
        ({"output_sats": (50_000_000, 1)}, "outputs exceed inputs"),
        ({"fee_sats": 7}, "fee disagrees"),
        ({"src_port": None}, "all present or all absent"),
        ({"ts_us": 1_000}, "genesis"),
        ({"output_addresses": ("x",), "output_sats": (1,)}, "implausible address"),
        ({"geo_country_src": "IND"}, "alpha-2"),
        ({"output_script_types": (ScriptType.P2TR,)}, "differs in length"),
    ],
)
def test_contract_rejects_inconsistent_records(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        CanonicalRecord(**_record(**overrides))


@pytest.mark.security
@pytest.mark.parametrize(
    "hostile_address",
    ["<script>alert(1)</script>", "bc1q'; DROP TABLE tx;--", "../../etc/passwd", "a" * 200, "bc1q\x00null"],
)
def test_injection_shaped_addresses_rejected(hostile_address: str) -> None:
    with pytest.raises(ValidationError):
        CanonicalRecord(**_record(output_addresses=(hostile_address, P2PKH)))


def test_unknown_fields_forbidden() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        CanonicalRecord(**_record(owner="someone"))
