from __future__ import annotations

from decimal import Decimal

from sutradhar_schemas.canonical import canonical_json, sha256_file, sha256_hex, sha256_json


def test_canonical_json_is_order_independent() -> None:
    assert (
        canonical_json({"b": 1, "a": [1, 2]}) == canonical_json({"a": [1, 2], "b": 1}) == b'{"a":[1,2],"b":1}'
    )


def test_floats_rounded_and_negative_zero_collapsed() -> None:
    assert canonical_json({"p": 0.1234567891, "z": -0.0}) == b'{"p":0.123457,"z":0.0}'


def test_decimal_and_sets_are_stable() -> None:
    assert canonical_json({"d": Decimal("1.50"), "s": {3, 1, 2}}) == b'{"d":"1.50","s":[1,2,3]}'


def test_hashes(tmp_path) -> None:
    path = tmp_path / "f.bin"
    path.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_hex(b"abc") == sha256_hex("abc") == sha256_file(path) == expected
    assert sha256_json({"x": 1}) == sha256_json({"x": 1})
