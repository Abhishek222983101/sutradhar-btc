"""The app database (blueprint §4.9), as typed SQLAlchemy models. The DDL itself lives in the Alembic
migrations (dialect-specific checks and audit triggers); `test_models_match_migrations` keeps the two equal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sutradhar_api.db import UTCDateTime, utcnow

JsonType = JSON().with_variant(JSONB(), "postgresql")
BigId = BigInteger().with_variant(Integer(), "sqlite")


NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JsonType,
        list[Any]: JsonType,
        datetime: UTCDateTime,
    }


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]


class AuthSession(Base):
    """One login = one refresh-token family. Revoking it ends every token in the family (and access tokens,
    which are checked against it on each request)."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(Text)
    client_ip: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)


class RefreshToken(Base):
    """Rotated records are kept until the family expires: finding one again *is* reuse detection."""

    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(Text, primary_key=True)  # public selector
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    secret_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    rotated_at: Mapped[datetime | None]


class MappingProfileRow(Base):
    __tablename__ = "mapping_profiles"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_mapping_profiles_name"),)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    spec: Mapped[dict[str, Any]]
    spec_sha256: Mapped[str] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    series_id: Mapped[str | None] = mapped_column(Text)
    profile_id: Mapped[str | None] = mapped_column(ForeignKey("mapping_profiles.id"))
    raw_digest: Mapped[str | None] = mapped_column(Text)
    normalised_digest: Mapped[str | None] = mapped_column(Text)
    xray: Mapped[dict[str, Any] | None]
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    reject_count: Mapped[int | None] = mapped_column(BigInteger)
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None]
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DatasetFile(Base):
    __tablename__ = "dataset_files"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    filename: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    prev_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    status: Mapped[str] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]]
    model_versions: Mapped[dict[str, Any]]
    refdata_versions: Mapped[dict[str, Any]]
    manifest: Mapped[dict[str, Any] | None]
    result_digest: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "ix_jobs_ready",
            "priority",
            "created_at",
            sqlite_where=text("status = 'queued'"),
            postgresql_where=text("status = 'queued'"),
        ),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    status: Mapped[str] = mapped_column(Text, default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None]
    heartbeat_at: Mapped[datetime | None]
    result: Mapped[dict[str, Any] | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job_id", "job_id", "id"), {"sqlite_autoincrement": True})
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    ts: Mapped[datetime] = mapped_column(default=utcnow)
    kind: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]]


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("run_id", "lead_key", name="uq_leads_run_id"),
        Index("ix_leads_queue", "run_id", "priority", "id"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    lead_key: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_ref: Mapped[str] = mapped_column(Text)
    p: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(Text)
    priority: Mapped[float] = mapped_column(Float)
    families: Mapped[list[Any]]
    reasons: Mapped[list[Any]]
    value_at_risk_sats: Mapped[int] = mapped_column(BigInteger, default=0)
    last_activity_at: Mapped[datetime | None]
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    calibrated: Mapped[bool] = mapped_column(Boolean)
    model_version: Mapped[str] = mapped_column(Text)
    explanation: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class LeadState(Base):
    __tablename__ = "lead_state"
    lead_key: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, default="NEW")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    snooze_until: Mapped[datetime | None]
    last_seen_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    changed_since_review: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class SettingRow(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]]
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_action", "action", "actor_id", "ts"),)
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    ts: Mapped[datetime]
    actor_id: Mapped[str | None] = mapped_column(Text)
    actor_role: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target_kind: Mapped[str] = mapped_column(Text)
    target_ref: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class AuditHead(Base):
    __tablename__ = "audit_head"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    seq: Mapped[int] = mapped_column(BigInteger)
    entry_hash: Mapped[str] = mapped_column(String(64))


class MergeDecision(Base):
    """An analyst's verdict on a merge suggestion; it survives re-runs because it is keyed by the cluster pair."""

    __tablename__ = "merge_decisions"
    __table_args__ = (
        UniqueConstraint("a_ref", "b_ref", name="uq_merge_decisions_a_ref"),
        CheckConstraint("decision IN ('accept', 'reject')", name="decision"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    a_ref: Mapped[str] = mapped_column(Text)
    b_ref: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("name", name="uq_watchlists_name"),
        CheckConstraint("kind IN ('address', 'ip')", name="kind"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "value", name="uq_watchlist_items_watchlist_id"),
        CheckConstraint(
            "category IN ('ransomware', 'darknet', 'scam', 'theft', 'sanctioned', 'mixer', 'other')",
            name="category",
        ),
        CheckConstraint("confidence > 0 AND confidence <= 1", name="confidence"),
        Index("ix_watchlist_items_watchlist_id_id", "watchlist_id", "id"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id"))
    value: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    added_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(default=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("verdict IN ('confirm', 'dismiss', 'escalate')", name="verdict"),
        CheckConstraint("verdict <> 'dismiss' OR reason_code IS NOT NULL", name="dismiss_reason"),
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('benign_service', 'victim', 'duplicate', 'insufficient_evidence',"
            " 'known_false_positive_pattern', 'other')",
            name="reason_code",
        ),
        Index("ix_feedback_lead_key", "lead_key", "created_at"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    lead_key: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    verdict: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (CheckConstraint("status IN ('open', 'closed', 'archived')", name="status"),)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="open")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    closed_at: Mapped[datetime | None]


class CaseItem(Base):
    __tablename__ = "case_items"
    __table_args__ = (
        UniqueConstraint("case_id", "item_kind", "ref", "run_id", name="uq_case_items_case_id"),
        CheckConstraint("item_kind IN ('lead', 'actor', 'address', 'tx', 'ip', 'chain')", name="kind"),
        Index("ix_case_items_case_id_added_at", "case_id", "added_at"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    item_kind: Mapped[str] = mapped_column(Text)
    ref: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    note: Mapped[str | None] = mapped_column(Text)
    added_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(default=utcnow)


class CaseNote(Base):
    __tablename__ = "case_notes"
    __table_args__ = (Index("ix_case_notes_case_id_created_at", "case_id", "created_at"),)
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body_md: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Export(Base):
    __tablename__ = "exports"
    __table_args__ = (
        CheckConstraint("kind IN ('evidence_pack', 'misp', 'stix', 'graphml', 'i2csv', 'pdf')", name="kind"),
        CheckConstraint("status IN ('queued', 'ready', 'failed')", name="status"),
    )
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued")
    file_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    manifest: Mapped[dict[str, Any] | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    file_sha256: Mapped[str] = mapped_column(Text)
    result: Mapped[dict[str, Any]]
    verified_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
