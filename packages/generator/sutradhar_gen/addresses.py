"""Syntactically valid Bitcoin mainnet addresses from random payloads.

Encoders follow the BIP-173 (bech32) / BIP-350 (bech32m) reference algorithm and Base58Check. The
payloads are random bytes, not real keys: the addresses are valid in form and own no real coins.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Final

import numpy as np

from sutradhar_schemas.enums import ScriptType

_CHARSET: Final = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_B58: Final = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BECH32_CONST: Final = 1
_BECH32M_CONST: Final = 0x2BC830A3
_GEN: Final = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
HRP: Final = "bc"


class Bech32Variant(Enum):
    BECH32 = _BECH32_CONST
    BECH32M = _BECH32M_CONST


def _polymod(values: list[int]) -> int:
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i, gen in enumerate(_GEN):
            chk ^= gen if ((top >> i) & 1) else 0
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convertbits(data: bytes | list[int], frombits: int, tobits: int, *, pad: bool) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("invalid value for bit conversion")
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid padding")
    return ret


def segwit_encode(witver: int, program: bytes, hrp: str = HRP) -> str:
    variant = Bech32Variant.BECH32 if witver == 0 else Bech32Variant.BECH32M
    data = [witver, *_convertbits(program, 8, 5, pad=True)]
    polymod = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ variant.value
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_CHARSET[d] for d in data + checksum)


def segwit_decode(address: str, hrp: str = HRP) -> tuple[int, bytes]:
    """Decode and verify a segwit address. Raises ValueError when the checksum or form is wrong."""
    if address.lower() != address and address.upper() != address:
        raise ValueError("mixed case")
    address = address.lower()
    pos = address.rfind("1")
    if pos < 1 or pos + 7 > len(address) or len(address) > 90 or address[:pos] != hrp:
        raise ValueError("bad bech32 structure")
    try:
        data = [_CHARSET.index(c) for c in address[pos + 1 :]]
    except ValueError as exc:
        raise ValueError("bad bech32 character") from exc
    const = _polymod(_hrp_expand(hrp) + data)
    witver = data[0]
    expected = _BECH32_CONST if witver == 0 else _BECH32M_CONST
    if const != expected:
        raise ValueError("bad checksum")
    program = bytes(_convertbits(data[1:-6], 5, 8, pad=False))
    if not 2 <= len(program) <= 40 or (witver == 0 and len(program) not in (20, 32)):
        raise ValueError("bad witness program length")
    return witver, program


def _b58encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    out = ""
    while number > 0:
        number, rem = divmod(number, 58)
        out = _B58[rem] + out
    pad = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * pad + out


def _b58decode(text: str) -> bytes:
    number = 0
    for char in text:
        number = number * 58 + _B58.index(char)
    pad = len(text) - len(text.lstrip("1"))
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\x00" * pad + body


def _checksum(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]


def base58check_encode(version: int, payload: bytes) -> str:
    data = bytes([version]) + payload
    return _b58encode(data + _checksum(data))


def base58check_decode(address: str) -> tuple[int, bytes]:
    raw = _b58decode(address)
    if len(raw) != 25 or _checksum(raw[:-4]) != raw[-4:]:
        raise ValueError("bad base58check address")
    return raw[0], raw[1:-4]


_PAYLOAD_LEN: Final = {
    ScriptType.P2PKH: 20,
    ScriptType.P2SH: 20,
    ScriptType.P2WPKH: 20,
    ScriptType.P2WSH: 32,
    ScriptType.P2TR: 32,
}


def make_address(script: ScriptType, rng: np.random.Generator) -> str:
    """A valid-format mainnet address of the given script type from random payload bytes."""
    payload = rng.bytes(_PAYLOAD_LEN[script])
    match script:
        case ScriptType.P2PKH:
            return base58check_encode(0x00, payload)
        case ScriptType.P2SH:
            return base58check_encode(0x05, payload)
        case ScriptType.P2WPKH | ScriptType.P2WSH:
            return segwit_encode(0, payload)
        case ScriptType.P2TR:
            return segwit_encode(1, payload)
    raise ValueError(f"cannot make an address for {script}")


def script_of(address: str) -> ScriptType:
    """Script type from address form (mirrors the engine's inference, used for generator self-checks)."""
    if address.startswith("bc1q"):
        return ScriptType.P2WPKH if len(address) == 42 else ScriptType.P2WSH
    if address.startswith("bc1p"):
        return ScriptType.P2TR
    if address.startswith("1"):
        return ScriptType.P2PKH
    if address.startswith("3"):
        return ScriptType.P2SH
    return ScriptType.UNKNOWN
