"""Mapping profiles shipped with the engine (blueprint §17.6)."""

from __future__ import annotations

from sutradhar_schemas.profile import MappingProfile

_ARRAY_JSON = {"encoding": "json"}

CANONICAL_CSV = MappingProfile.model_validate(
    {
        "profile": "canonical-v1",
        "version": 1,
        "format": "csv",
        "timestamp": {"field": "timestamp", "unit": "auto", "tz": "UTC"},
        "amount_unit": "btc",
        "fields": {
            "txid": {"field": "txid", "transform": "lower"},
            "src_ip": {"field": "src_ip", "optional": True},
            "src_port": {"field": "src_port", "cast": "int", "optional": True},
            "dst_ip": {"field": "dst_ip", "optional": True},
            "dst_port": {"field": "dst_port", "cast": "int", "optional": True},
            "input_addresses": {"field": "input_addresses", "array": _ARRAY_JSON},
            "input_amounts": {"field": "input_amounts", "array": _ARRAY_JSON},
            "output_addresses": {"field": "output_addresses", "array": _ARRAY_JSON},
            "output_amounts": {"field": "output_amounts", "array": _ARRAY_JSON},
            "fee": {"field": "fee", "optional": True},
            "script_type": {"field": "script_type", "optional": True},
            "geo_country": {"field": "geo_country", "optional": True},
            "asn": {"field": "asn", "optional": True, "transform": "strip_as_prefix"},
        },
    }
)

BUILTIN_PROFILES: dict[str, MappingProfile] = {CANONICAL_CSV.profile: CANONICAL_CSV}
