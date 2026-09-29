"""Evidence envelopes, leads, manifests and capability profiles — the typed shapes the engine emits."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sutradhar_schemas.enums import Family, Grade, LeadType, Method, ObservationModel


class EvidenceRefs(BaseModel):
    """Pointers back to source material. `obs` are (file_id, row_no) pairs of the original upload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    txids: tuple[str, ...] = ()
    obs: tuple[tuple[str, int], ...] = ()
    rules: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class EvidenceEnvelope(BaseModel):
    """Carried by every derived edge or claim (invariant I2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Method
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: EvidenceRefs = EvidenceRefs()
    model_version: str = Field(min_length=1, max_length=64, examples=["origin_ranker@1.3.0", "rules@1"])
    run_id: str = Field(min_length=1, max_length=64)


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    family: Family
    feature: str
    value: float | int | str | None = None
    contribution: float = Field(description="Log-odds contribution to the model score")
    text: str = Field(min_length=1, max_length=400)


class LeadSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lead_key: str = Field(min_length=16, max_length=16)
    type: LeadType
    subject_kind: str
    subject_ref: str
    p: float = Field(ge=0.0, le=1.0)
    grade: Grade
    priority: float
    families: tuple[Family, ...] = Field(min_length=1)
    reasons: tuple[Reason, ...] = Field(min_length=1)
    value_at_risk_sats: int = Field(default=0, ge=0)
    title: str
    summary: str


class StageStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ms: int = Field(ge=0)
    rows: dict[str, int] = {}
    notes: list[str] = []


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    files: list[dict[str, Any]]
    profile_ref: str
    profile_sha256: str
    raw_digest: str
    normalised_digest: str
    contract_version: str
    row_counts: dict[str, int]


class RunManifest(BaseModel):
    """The single document that makes a run reproducible (blueprint §4.10)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    dataset: dict[str, str]
    code: dict[str, str]
    models: dict[str, str] = {}
    model_sha256: dict[str, str] = {}
    refdata: dict[str, str] = {}
    config: dict[str, Any] = {}
    stages: dict[str, StageStat] = {}
    result_tables: list[str] = []
    result_digest: str = ""


class NetworkCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool
    observation_model: ObservationModel
    distinct_src_ips: int = 0
    distinct_dst_ips: int = 0
    dst_8333_share: float = 0.0
    obs_per_tx_p50: float = 0.0
    obs_per_tx_p90: float = 0.0
    sensors_inferred: int = 0


class CapabilityProfile(BaseModel):
    """What a dataset allows the engine to do; rendered as the Dataset X-ray (blueprint §4.5)."""

    model_config = ConfigDict(extra="forbid")

    rows: int
    txs: int
    addresses: int
    ips: int
    span_from_us: int | None = None
    span_to_us: int | None = None
    amount_unit: dict[str, Any] = {}
    network: NetworkCapability
    fields: dict[str, str] = {}
    quality: dict[str, float | int] = {}
    enabled_stages: list[str] = []
    disabled_features: list[str] = []
    warnings: list[str] = []
