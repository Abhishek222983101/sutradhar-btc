"""Script-type inference from address form (blueprint §4.3.3). Never guesses: unknown forms stay unknown."""

from __future__ import annotations

from sutradhar_schemas.enums import ScriptType

_SEGWIT_HRPS = ("bcrt1", "bc1", "tb1")
_V0_BY_BODY_LEN = {39: ScriptType.P2WPKH, 59: ScriptType.P2WSH}
_BASE58_BY_FIRST = {
    "1": ScriptType.P2PKH,
    "m": ScriptType.P2PKH,
    "n": ScriptType.P2PKH,
    "3": ScriptType.P2SH,
    "2": ScriptType.P2SH,
}


def infer_script_type(address: str) -> ScriptType:
    lower = address.lower()
    hrp = next((h for h in _SEGWIT_HRPS if lower.startswith(h) and len(lower) > len(h)), None)
    if hrp is not None:
        witver = lower[len(hrp)]
        body_len = len(lower) - len(hrp)
        if witver == "q":
            return _V0_BY_BODY_LEN.get(body_len, ScriptType.UNKNOWN)
        return ScriptType.P2TR if witver == "p" else ScriptType.UNKNOWN
    if 25 <= len(address) <= 35:
        return _BASE58_BY_FIRST.get(address[0], ScriptType.UNKNOWN)
    return ScriptType.UNKNOWN
