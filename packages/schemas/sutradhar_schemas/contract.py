"""Data contract v1 (blueprint §4.2).

Two layers:

* **Input fields** — the logical names a mapping profile maps any source layout onto (``timestamp``,
  ``input_amounts`` …). These are the PS minimum fields plus optional extras.
* **CanonicalRecord** — one *normalised* observation: satoshis, UTC microseconds, canonical IPs,
  lower-case txid. Bulk ingestion uses columnar code; this model is the typed reference used by the API,
  tests and documentation, and it applies the same rules.

Changing this module is a contract change: it requires an ADR (see docs/adr).
"""

from __future__ import annotations

import ipaddress
import re
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sutradhar_schemas.enums import ScriptType
from sutradhar_schemas.units import GENESIS_US, Sats, TsUs

CONTRACT_VERSION: Final = "1.0.0"

# The problem statement's minimum field list, verbatim.
PS_MINIMUM_FIELDS: Final = (
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "txid",
    "input_addresses",
    "output_addresses",
    "input_amounts",
    "output_amounts",
    "geo_country",
    "asn",
)

# Logical input fields a mapping profile can target.
REQUIRED_INPUT_FIELDS: Final = (
    "timestamp",
    "txid",
    "input_addresses",
    "output_addresses",
    "input_amounts",
    "output_amounts",
)
NETWORK_INPUT_FIELDS: Final = ("src_ip", "dst_ip", "src_port", "dst_port")
OPTIONAL_INPUT_FIELDS: Final = (
    "fee",
    "script_type",
    "input_script_types",
    "output_script_types",
    "geo_country",
    "asn",
    "input_prevouts",
    "block_height",
    "block_time",
    "vsize",
    "locktime",
    "version",
    "rbf",
    "sensor_id",
)
ARRAY_INPUT_FIELDS: Final = (
    "input_addresses",
    "output_addresses",
    "input_amounts",
    "output_amounts",
    "input_script_types",
    "output_script_types",
    "input_prevouts",
)
ALL_INPUT_FIELDS: Final = REQUIRED_INPUT_FIELDS + NETWORK_INPUT_FIELDS + OPTIONAL_INPUT_FIELDS

TXID_RE: Final = re.compile(r"^[0-9a-f]{64}$")
ADDRESS_RE: Final = re.compile(r"^[A-Za-z0-9]{14,90}$")
PREVOUT_RE: Final = re.compile(r"^[0-9a-f]{64}:\d{1,5}$")
COUNTRY_RE: Final = re.compile(r"^[A-Z]{2}$")


def canonical_ip(value: str) -> str:
    """Canonical text form of an IPv4/IPv6 address (IPv6 compressed, lower-case)."""
    return str(ipaddress.ip_address(value.strip()))


class CanonicalRecord(BaseModel):
    """One observed network event that carried a transaction, in canonical units."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    ts_us: TsUs = Field(description="Observation time, UTC microseconds.")
    txid: str = Field(description="Transaction id, 64 lower-case hex characters.")
    src_ip: str | None = None
    src_port: int | None = Field(default=None, ge=0, le=65535)
    dst_ip: str | None = None
    dst_port: int | None = Field(default=None, ge=0, le=65535)
    input_addresses: tuple[str, ...]
    input_sats: tuple[Sats, ...]
    output_addresses: tuple[str, ...] = Field(min_length=1)
    output_sats: tuple[Sats, ...] = Field(min_length=1)
    fee_sats: Sats | None = None
    input_script_types: tuple[ScriptType, ...] | None = None
    output_script_types: tuple[ScriptType, ...] | None = None
    input_prevouts: tuple[str, ...] | None = None
    geo_country_src: str | None = None
    asn_src: int | None = Field(default=None, ge=0, le=4_294_967_295)
    block_height: int | None = Field(default=None, ge=0)
    vsize: int | None = Field(default=None, ge=1)
    locktime: int | None = Field(default=None, ge=0)
    version: int | None = None
    rbf: bool | None = None
    sensor_id: str | None = Field(default=None, max_length=128)

    @field_validator("txid")
    @classmethod
    def _txid(cls, value: str) -> str:
        value = value.lower()
        if not TXID_RE.fullmatch(value):
            raise ValueError("txid must be 64 hex characters")
        return value

    @field_validator("src_ip", "dst_ip")
    @classmethod
    def _ip(cls, value: str | None) -> str | None:
        return None if value is None else canonical_ip(value)

    @field_validator("input_addresses", "output_addresses")
    @classmethod
    def _addresses(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for address in value:
            if not ADDRESS_RE.fullmatch(address):
                raise ValueError(f"implausible address: {address[:24]!r}")
        return value

    @field_validator("input_prevouts")
    @classmethod
    def _prevouts(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is not None:
            for prevout in value:
                if not PREVOUT_RE.fullmatch(prevout.lower()):
                    raise ValueError("prevout must be 'txid:vout'")
            value = tuple(prevout.lower() for prevout in value)
        return value

    @field_validator("geo_country_src")
    @classmethod
    def _country(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.upper()
            if not COUNTRY_RE.fullmatch(value):
                raise ValueError("country must be an ISO-3166 alpha-2 code")
        return value

    @field_validator("ts_us")
    @classmethod
    def _after_genesis(cls, value: int) -> int:
        if value < GENESIS_US:
            raise ValueError("timestamp is before the Bitcoin genesis block")
        return value

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        if len(self.input_addresses) != len(self.input_sats):
            raise ValueError("input_addresses and input_amounts differ in length")
        if len(self.output_addresses) != len(self.output_sats):
            raise ValueError("output_addresses and output_amounts differ in length")
        for name, types, addresses in (
            ("input_script_types", self.input_script_types, self.input_addresses),
            ("output_script_types", self.output_script_types, self.output_addresses),
        ):
            if types is not None and len(types) != len(addresses):
                raise ValueError(f"{name} differs in length from its addresses")
        if self.input_prevouts is not None and len(self.input_prevouts) != len(self.input_addresses):
            raise ValueError("input_prevouts differs in length from input_addresses")
        if self.input_sats:  # coinbase transactions have no inputs
            fee = sum(self.input_sats) - sum(self.output_sats)
            if fee < 0:
                raise ValueError("outputs exceed inputs")
            if self.fee_sats is not None and abs(self.fee_sats - fee) > 1:
                raise ValueError("fee disagrees with inputs minus outputs")
        has_network = [self.src_ip, self.dst_ip, self.src_port, self.dst_port]
        if any(v is not None for v in has_network) and not all(v is not None for v in has_network):
            raise ValueError("network fields must be all present or all absent")
        return self

    @property
    def is_coinbase(self) -> bool:
        return len(self.input_addresses) == 0

    @property
    def computed_fee_sats(self) -> int:
        return 0 if self.is_coinbase else sum(self.input_sats) - sum(self.output_sats)
