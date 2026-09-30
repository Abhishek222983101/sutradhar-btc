"""Auto-mapper: propose a mapping profile for a file whose columns are not named like the canonical layout.

Matching is by normalised column name against a synonym table, then confirmed on sample values (an IP column must
hold IPs, a txid column 64 hex characters, ...). The result carries a per-field confidence and anything it could not
place, so the analyst reviews it rather than trusting it blindly.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any

from sutradhar_schemas.contract import ALL_INPUT_FIELDS
from sutradhar_schemas.enums import FileFormat
from sutradhar_schemas.profile import MappingProfile

SYNONYMS: dict[str, tuple[str, ...]] = {
    "timestamp": (
        "timestamp",
        "time",
        "ts",
        "datetime",
        "date",
        "seen_at",
        "observed_at",
        "first_seen",
        "epoch",
    ),
    "txid": ("txid", "tx_id", "txhash", "tx_hash", "hash", "transaction_id", "transaction_hash"),
    "src_ip": ("src_ip", "source_ip", "srcip", "src", "from_ip", "peer_ip", "remote_ip", "client_ip"),
    "dst_ip": (
        "dst_ip",
        "destination_ip",
        "dest_ip",
        "dstip",
        "dst",
        "to_ip",
        "local_ip",
        "sensor_ip",
        "server_ip",
    ),
    "src_port": (
        "src_port",
        "source_port",
        "sport",
        "srcport",
        "from_port",
        "remote_port",
        "peer_port",
        "client_port",
    ),
    "dst_port": (
        "dst_port",
        "destination_port",
        "dest_port",
        "dport",
        "dstport",
        "to_port",
        "local_port",
        "sensor_port",
        "server_port",
    ),
    "input_addresses": (
        "input_addresses",
        "inputs",
        "in_addresses",
        "input_addrs",
        "vin_addresses",
        "senders",
    ),
    "input_amounts": ("input_amounts", "in_amounts", "input_values", "vin_values", "input_btc", "input_sats"),
    "output_addresses": (
        "output_addresses",
        "outputs",
        "out_addresses",
        "output_addrs",
        "vout_addresses",
        "receivers",
    ),
    "output_amounts": (
        "output_amounts",
        "out_amounts",
        "output_values",
        "vout_values",
        "output_btc",
        "output_sats",
    ),
    "fee": ("fee", "fees", "tx_fee", "fee_btc", "fee_sats"),
    "script_type": ("script_type", "scripttype", "address_type", "script"),
    "geo_country": ("geo_country", "country", "country_code", "cc", "src_country"),
    "asn": ("asn", "as_number", "autonomous_system", "src_asn"),
}
_ARRAYS = {"input_addresses", "input_amounts", "output_addresses", "output_amounts"}
_NORM = re.compile(r"[^a-z0-9]+")
_TXID = re.compile(r"[0-9a-fA-F]{64}")


def _norm(name: str) -> str:
    return _NORM.sub("_", name.strip().lower()).strip("_")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return True


def _confirm(target: str, samples: list[str]) -> bool:
    """Do the sample values look like this field? An empty sample confirms nothing (name match only)."""
    vals = [v for v in samples if v not in ("", None)]
    if not vals:
        return True
    if target == "txid":
        return all(_TXID.fullmatch(v.strip()) for v in vals)
    if target in ("src_ip", "dst_ip"):
        return all(_is_ip(v) for v in vals)
    if target in ("src_port", "dst_port"):
        return all(v.strip().isdigit() for v in vals)
    if target in _ARRAYS:
        return all(v.strip().startswith("[") or "|" in v or ";" in v or "," in v for v in vals)
    return True


@dataclass
class AutoMapResult:
    profile: MappingProfile | None
    matched: dict[str, tuple[str, float]] = field(default_factory=dict)  # target -> (column, confidence)
    missing_required: list[str] = field(default_factory=list)
    unmatched_columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def propose_profile(
    columns: list[str], samples: dict[str, list[str]], fmt: FileFormat = FileFormat.CSV
) -> AutoMapResult:
    norm = {c: _norm(c) for c in columns}
    used: set[str] = set()
    matched: dict[str, tuple[str, float]] = {}
    for target in ALL_INPUT_FIELDS:
        best: tuple[str, float] | None = None
        for col, n in norm.items():
            if col in used:
                continue
            if n in SYNONYMS.get(target, ()):
                conf = 1.0 if n == target else 0.9
                if _confirm(target, samples.get(col, [])) and (best is None or conf > best[1]):
                    best = (col, conf)
        if best:
            used.add(best[0])
            matched[target] = best
    required = ["timestamp", "txid", "input_addresses", "input_amounts", "output_addresses", "output_amounts"]
    missing = [t for t in required if t not in matched]
    result = AutoMapResult(None, matched, missing, [c for c in columns if c not in used])
    if missing:
        result.notes.append("required fields not found: " + ", ".join(missing))
        return result
    amounts = " ".join(v for t in ("input_amounts", "output_amounts") for v in samples.get(matched[t][0], []))
    unit = "sat" if re.search(r"(?<![\d.])\d{7,}(?![\d.])", amounts) and "." not in amounts else "btc"
    if "sats" in norm.get(matched["input_amounts"][0], ""):
        unit = "sat"
    result.notes.append(f"amount unit guessed as {unit} from sample values")
    fields: dict[str, Any] = {}
    for target, (col, _) in matched.items():
        if target == "timestamp":
            continue
        spec: dict[str, Any] = {"field": col}
        if target == "txid":
            spec["transform"] = "lower"
        if target in _ARRAYS:
            sample = next((v for v in samples.get(col, []) if v), "[")
            spec["array"] = (
                {"encoding": "json"}
                if sample.strip().startswith("[")
                else {"encoding": "delimited", "sep": "|" if "|" in sample else ";" if ";" in sample else ","}
            )
        elif target in ("src_port", "dst_port"):
            spec["cast"] = "int"
        if target not in ("txid", *_ARRAYS):
            spec["optional"] = True
        if target == "asn":
            spec["transform"] = "strip_as_prefix"
        fields[target] = spec
    result.profile = MappingProfile.model_validate(
        {
            "profile": "auto-mapped",
            "version": 1,
            "format": str(fmt),
            "timestamp": {"field": matched["timestamp"][0], "unit": "auto", "tz": "UTC"},
            "amount_unit": unit,
            "fields": fields,
        }
    )
    return result
