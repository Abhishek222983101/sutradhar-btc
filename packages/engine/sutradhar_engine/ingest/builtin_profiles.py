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


def _variant(name: str, fmt: str, **extra: object) -> MappingProfile:
    return MappingProfile.model_validate(
        {**CANONICAL_CSV.model_dump(mode="json"), "profile": name, "format": fmt, **extra}
    )


CANONICAL_JSON = _variant("canonical-json-v1", "json")
CANONICAL_NDJSON = _variant("canonical-ndjson-v1", "ndjson")
CANONICAL_XML = _variant("canonical-xml-v1", "xml", xml={"record_tag": "record"})

BUILTIN_PROFILES: dict[str, MappingProfile] = {
    p.profile: p for p in (CANONICAL_CSV, CANONICAL_JSON, CANONICAL_NDJSON, CANONICAL_XML)
}
PROFILE_BY_EXTENSION = {
    ".csv": "canonical-v1",
    ".tsv": "canonical-v1",
    ".txt": "canonical-v1",
    ".json": "canonical-json-v1",
    ".ndjson": "canonical-ndjson-v1",
    ".jsonl": "canonical-ndjson-v1",
    ".xml": "canonical-xml-v1",
}
