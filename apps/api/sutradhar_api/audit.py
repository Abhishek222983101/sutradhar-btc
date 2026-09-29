"""I5 — the append-only, hash-chained audit log (blueprint §8.6).

`append()` runs inside the caller's transaction, so the audit entry and the change it records commit together
(I13). The head row is locked while the next sequence number is taken, which keeps the chain gapless.
`verify()` recomputes every hash from the stored fields and checks the head points at the last entry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sutradhar_api.db import utcnow
from sutradhar_api.models import AuditHead, AuditLog
from sutradhar_schemas.canonical import canonical_json, sha256_hex

GENESIS = "0" * 64
SYSTEM = "system"


def _ts_text(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _entry_hash(
    *,
    seq: int,
    ts: datetime,
    actor_id: str | None,
    actor_role: str,
    action: str,
    target_kind: str,
    target_ref: str,
    payload: Mapping[str, Any],
    prev: str,
) -> str:
    body = canonical_json(
        {
            "seq": seq,
            "ts": _ts_text(ts),
            "actor": actor_id,
            "role": actor_role,
            "action": action,
            "target": [target_kind, target_ref],
            "payload": dict(payload),
            "prev": prev,
        }
    )
    return sha256_hex(body)


def append(
    session: Session,
    *,
    actor_id: str | None,
    actor_role: str,
    action: str,
    target_kind: str,
    target_ref: str,
    payload: Mapping[str, Any] | None = None,
) -> AuditLog:
    head = session.execute(select(AuditHead).where(AuditHead.id == 1).with_for_update()).scalar_one()
    seq = head.seq + 1
    ts = utcnow()
    body_payload = dict(payload or {})
    entry_hash = _entry_hash(
        seq=seq,
        ts=ts,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_kind=target_kind,
        target_ref=target_ref,
        payload=body_payload,
        prev=head.entry_hash,
    )
    entry = AuditLog(
        seq=seq,
        ts=ts,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_kind=target_kind,
        target_ref=target_ref,
        payload=body_payload,
        prev_hash=head.entry_hash,
        entry_hash=entry_hash,
    )
    session.add(entry)
    head.seq, head.entry_hash = seq, entry_hash
    session.flush()
    return entry


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    entries: int
    head: str
    broken_at: int | None = None
    reason: str | None = None


def verify(session: Session, *, batch: int = 1000) -> VerifyResult:
    prev, expected_seq, count = GENESIS, 1, 0
    rows = session.execute(select(AuditLog).order_by(AuditLog.seq).execution_options(yield_per=batch))
    for row in rows.scalars():
        if row.seq != expected_seq:
            return VerifyResult(False, count, prev, row.seq, f"gap: expected seq {expected_seq}")
        recomputed = _entry_hash(
            seq=row.seq,
            ts=row.ts,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            action=row.action,
            target_kind=row.target_kind,
            target_ref=row.target_ref,
            payload=row.payload,
            prev=prev,
        )
        if row.prev_hash != prev:
            return VerifyResult(False, count, prev, row.seq, "prev_hash does not match the previous entry")
        if recomputed != row.entry_hash:
            return VerifyResult(False, count, prev, row.seq, "entry content does not match its hash")
        prev, expected_seq, count = row.entry_hash, expected_seq + 1, count + 1
    head = session.execute(select(AuditHead).where(AuditHead.id == 1)).scalar_one()
    if head.seq != count or head.entry_hash != prev:
        return VerifyResult(
            False, count, prev, head.seq, "head does not point at the last entry (truncated?)"
        )
    return VerifyResult(True, count, prev)
