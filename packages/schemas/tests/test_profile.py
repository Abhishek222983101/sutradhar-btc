"""Mapping profiles are validated data: known targets, required fields, allow-listed transforms only."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from sutradhar_schemas import MappingProfile


def _spec(**overrides: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "profile": "canonical-v1",
        "version": 1,
        "format": "csv",
        "fields": {
            "txid": {"field": "txid"},
            "src_ip": {"field": "src_ip"},
            "input_addresses": {"field": "input_addresses", "array": {"encoding": "json"}},
            "input_amounts": {"field": "input_amounts", "array": {"encoding": "json"}},
            "output_addresses": {"field": "output_addresses", "array": {"encoding": "json"}},
            "output_amounts": {"field": "output_amounts", "array": {"encoding": "json"}},
        },
    }
    spec.update(overrides)
    return spec


def test_valid_profile() -> None:
    profile = MappingProfile.model_validate(_spec())
    assert profile.ref == "canonical-v1@1"
    assert len(profile.spec_sha256()) == 64


def test_profile_hash_stable() -> None:
    spec = _spec()
    reordered = {key: spec[key] for key in reversed(list(spec))}
    reordered["fields"] = dict(reversed(list(spec["fields"].items())))
    assert (
        MappingProfile.model_validate(spec).spec_sha256()
        == MappingProfile.model_validate(reordered).spec_sha256()
    )


def test_hash_changes_when_mapping_changes() -> None:
    changed = _spec()
    changed["fields"]["txid"] = {"field": "tx_hash"}
    assert (
        MappingProfile.model_validate(_spec()).spec_sha256()
        != MappingProfile.model_validate(changed).spec_sha256()
    )


def test_unknown_target_field_rejected() -> None:
    spec = _spec()
    spec["fields"]["owner_name"] = {"field": "x"}
    with pytest.raises(ValidationError, match="unknown target fields"):
        MappingProfile.model_validate(spec)


def test_missing_required_field_rejected() -> None:
    spec = _spec()
    del spec["fields"]["txid"]
    with pytest.raises(ValidationError, match="required fields"):
        MappingProfile.model_validate(spec)


def test_array_fields_need_array_spec() -> None:
    spec = _spec()
    spec["fields"]["input_addresses"] = {"field": "input_addresses"}
    with pytest.raises(ValidationError, match="array field"):
        MappingProfile.model_validate(spec)


def test_indexed_arrays_need_prefix() -> None:
    spec = _spec()
    spec["fields"]["input_addresses"] = {"field": "input_address", "array": {"encoding": "indexed"}}
    with pytest.raises(ValidationError, match="index_prefix"):
        MappingProfile.model_validate(spec)


@pytest.mark.security
@pytest.mark.parametrize(
    "transform", ["__import__('os').system('id')", "eval", "exec", "lambda x: x", "os.system"]
)
def test_profiles_cannot_reference_code(transform: str) -> None:
    spec = _spec()
    spec["fields"]["txid"] = {"field": "txid", "transform": transform}
    with pytest.raises(ValidationError, match="unknown transform"):
        MappingProfile.model_validate(spec)


@pytest.mark.security
def test_profile_name_is_constrained() -> None:
    with pytest.raises(ValidationError):
        MappingProfile.model_validate(_spec(profile="../../etc/passwd"))
