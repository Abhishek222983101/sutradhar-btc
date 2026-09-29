"""Generated addresses are valid mainnet forms; encoders match the BIP-173/350 reference vectors."""

from __future__ import annotations

import numpy as np
import pytest

from sutradhar_gen.addresses import (
    base58check_decode,
    base58check_encode,
    make_address,
    script_of,
    segwit_decode,
    segwit_encode,
)
from sutradhar_schemas.enums import ScriptType


def test_bip173_and_bip350_vectors() -> None:
    p2wpkh = segwit_encode(0, bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6"))
    assert p2wpkh == "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    p2tr = segwit_encode(1, bytes.fromhex("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"))
    assert p2tr == "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
    assert segwit_decode(p2wpkh) == (0, bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6"))


@pytest.mark.parametrize("script", [s for s in ScriptType if s != ScriptType.UNKNOWN])
def test_addresses_valid_format(script: ScriptType) -> None:
    rng = np.random.default_rng(7)
    for _ in range(200):
        address = make_address(script, rng)
        assert script_of(address) == script
        if address.startswith("bc1"):
            witver, program = segwit_decode(address)
            assert witver == (0 if script in (ScriptType.P2WPKH, ScriptType.P2WSH) else 1)
            assert len(program) == (20 if script == ScriptType.P2WPKH else 32)
        else:
            version, payload = base58check_decode(address)
            assert version == (0x00 if script == ScriptType.P2PKH else 0x05)
            assert len(payload) == 20


def test_corrupted_checksums_are_detected() -> None:
    good = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    with pytest.raises(ValueError, match="checksum"):
        segwit_decode(good[:-1] + ("5" if good[-1] != "5" else "6"))
    legacy = base58check_encode(0, bytes(20))
    with pytest.raises(ValueError, match="base58check"):
        base58check_decode(legacy[:-1] + ("2" if legacy[-1] != "2" else "3"))
