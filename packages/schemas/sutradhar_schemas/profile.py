"""Mapping profiles: turn any source layout into the canonical input fields without code (blueprint §4.3.2).

Profiles are data. They can only reference an allow-listed set of transforms — nothing in a profile can
execute code.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sutradhar_schemas.canonical import sha256_json
from sutradhar_schemas.contract import ALL_INPUT_FIELDS, ARRAY_INPUT_FIELDS, REQUIRED_INPUT_FIELDS
from sutradhar_schemas.enums import FileFormat

TRANSFORMS: Final = frozenset({"lower", "upper", "strip", "strip_as_prefix"})

ArrayEncoding = Literal["native", "json", "delimited", "indexed", "xml_repeat"]
TimestampUnit = Literal["auto", "iso", "s", "ms", "us"]
AmountUnitSetting = Literal["auto", "btc", "sat"]
Cast = Literal["str", "int", "float", "bool"]


class ArraySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    encoding: ArrayEncoding = "native"
    sep: str = Field(default=";", min_length=1, max_length=3)
    index_prefix: str | None = Field(default=None, description="For 'indexed': columns named <prefix>0..n")

    @model_validator(mode="after")
    def _indexed_needs_prefix(self) -> Self:
        if self.encoding == "indexed" and not self.index_prefix:
            raise ValueError("indexed arrays need index_prefix")
        return self


class FieldMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(
        min_length=1, max_length=256, description="Source column / dotted JSON path / XML path"
    )
    cast: Cast | None = None
    optional: bool = False
    transform: str | None = None
    array: ArraySpec | None = None

    @field_validator("transform")
    @classmethod
    def _allowed_transform(cls, value: str | None) -> str | None:
        if value is not None and value not in TRANSFORMS:
            raise ValueError(f"unknown transform {value!r}; allowed: {sorted(TRANSFORMS)}")
        return value


class CsvOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    delimiter: str = Field(default=",", min_length=1, max_length=1)
    quote: str = Field(default='"', min_length=1, max_length=1)
    header: bool = True
    encoding: Literal["utf-8", "utf-8-sig", "latin-1"] = "utf-8"


class XmlOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_tag: str = Field(
        default="event", min_length=1, max_length=64, description="Element that is one record"
    )


class TimestampSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(default="timestamp", min_length=1, max_length=256)
    unit: TimestampUnit = "auto"
    tz: str = Field(default="UTC", description="Zone assumed for ISO timestamps without an offset")


class MappingProfile(BaseModel):
    """How to read one source layout. Versioned; the hash is recorded in every dataset manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    version: int = Field(default=1, ge=1)
    format: FileFormat
    csv: CsvOptions = CsvOptions()
    xml: XmlOptions = XmlOptions()
    timestamp: TimestampSpec = TimestampSpec()
    amount_unit: AmountUnitSetting = "auto"
    fields: dict[str, FieldMap]

    @field_validator("fields")
    @classmethod
    def _known_targets(cls, value: dict[str, FieldMap]) -> dict[str, FieldMap]:
        unknown = sorted(set(value) - set(ALL_INPUT_FIELDS))
        if unknown:
            raise ValueError(f"unknown target fields: {unknown}")
        return value

    @model_validator(mode="after")
    def _required_present(self) -> Self:
        missing = [name for name in REQUIRED_INPUT_FIELDS if name != "timestamp" and name not in self.fields]
        if missing:
            raise ValueError(f"profile does not map required fields: {missing}")
        for name, spec in self.fields.items():
            if name in ARRAY_INPUT_FIELDS and spec.array is None:
                raise ValueError(f"{name} is an array field; give it an array spec")
            if name not in ARRAY_INPUT_FIELDS and spec.array is not None:
                raise ValueError(f"{name} is a scalar field; remove its array spec")
        return self

    def spec_sha256(self) -> str:
        return sha256_json(self.model_dump(mode="json"))

    @property
    def ref(self) -> str:
        return f"{self.profile}@{self.version}"
