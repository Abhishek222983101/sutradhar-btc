"""Request and response bodies. Money is `*_sats` integers; times are UTC ISO-8601."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=128)


class UserOut(Out):
    id: str
    email: str
    name: str
    role: str
    permissions: list[str] = []


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime
    user: UserOut


class DatasetFileOut(Out):
    id: str
    filename: str
    format: str
    sha256: str
    bytes: int


class DatasetOut(Out):
    id: str
    name: str
    status: str
    source: str
    raw_digest: str | None
    normalised_digest: str | None
    row_count: int | None
    reject_count: int | None
    bytes: int | None
    error: str | None
    expires_at: datetime | None
    created_at: datetime


class DatasetDetail(DatasetOut):
    xray: dict[str, Any] | None
    files: list[DatasetFileOut]


class JobOut(Out):
    id: str
    kind: str
    status: str
    attempts: int
    cancel_requested: bool
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=4, max_length=80)


class RunOut(Out):
    id: str
    dataset_id: str
    status: str
    stage: str | None
    result_digest: str | None
    model_versions: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunOut):
    config: dict[str, Any]
    manifest: dict[str, Any] | None


class LeadStateOut(Out):
    status: str
    assignee_id: str | None
    changed_since_review: bool


class LeadOut(Out):
    id: str
    run_id: str
    lead_key: str
    type: str
    subject_kind: str
    subject_ref: str
    title: str
    summary: str
    p: float
    grade: str
    priority: float
    families: list[str]
    value_at_risk_sats: int
    last_activity_at: datetime | None
    calibrated: bool
    model_version: str
    state: LeadStateOut | None = None


class LeadDetail(LeadOut):
    reasons: list[dict[str, Any]]


class DatasetAccepted(BaseModel):
    dataset: DatasetOut
    job: JobOut


class RunAccepted(BaseModel):
    run: RunOut
    job: JobOut


class AuditVerifyOut(BaseModel):
    ok: bool
    entries: int
    head: str
    broken_at: int | None
    reason: str | None


class MergeDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(min_length=4, max_length=80)
    a: str = Field(min_length=8, max_length=100)
    b: str = Field(min_length=8, max_length=100)
    decision: Literal["accept", "reject"]
    reason: str = Field(min_length=3, max_length=500)


class MergeDecisionOut(Out):
    id: str
    a_ref: str
    b_ref: str
    decision: str
    reason: str
    run_id: str
    created_at: datetime
