"""Triage: move a lead through review, record the verdict and reason, and assign it (lead analysts).

Lead state is keyed by `lead_key`, so it survives re-runs. Demo visitors triage a private copy (keyed with their
user id), so they can never change what another visitor sees. A dismissal always needs a reason; the reason and the
verdict are training data for the ranker's feedback loop and are audited.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from sutradhar_api import audit
from sutradhar_api.access import can_see
from sutradhar_api.auth.permissions import Action, allowed
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import ReadDB, WriteDB, require
from sutradhar_api.models import Feedback, Lead, LeadState, Run, User
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import LeadStateOut, Out
from sutradhar_schemas.enums import Role
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1", tags=["triage"])
Reason = Literal[
    "benign_service", "victim", "duplicate", "insufficient_evidence", "known_false_positive_pattern", "other"
]
_VERDICT_STATUS = {"confirm": "CONFIRMED", "dismiss": "DISMISSED", "escalate": "ESCALATED"}


def state_key(principal: Principal, lead_key: str) -> str:
    """Demo visitors get a private copy of each lead's state."""
    return f"u:{principal.user.id}:{lead_key}" if principal.role == Role.DEMO else lead_key


class StateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["NEW", "IN_REVIEW", "SNOOZED"] | None = None
    assignee_id: str | None = Field(default=None, max_length=80)
    snooze_until: datetime | None = None
    clear_assignee: bool = False


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["confirm", "dismiss", "escalate"]
    reason_code: Reason | None = None
    note: str | None = Field(default=None, max_length=1000)
    run_id: str = Field(min_length=4, max_length=80)


class FeedbackOut(Out):
    id: str
    lead_key: str
    verdict: str
    reason_code: str | None
    note: str | None
    created_at: datetime


def _known_lead(db: Session, lead_key: str, principal: Principal) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.lead_key == lead_key).order_by(Lead.created_at.desc()).limit(1))
    run = db.get(Run, lead.run_id) if lead else None
    if lead is None or run is None or not can_see(run.created_by, principal):
        raise Problem(404, "not_found", "no such lead")
    return lead


def _state(db: Session, principal: Principal, lead_key: str) -> LeadState:
    key = state_key(principal, lead_key)
    row = db.get(LeadState, key)
    if row is None:
        row = LeadState(lead_key=key, status="NEW", changed_since_review=False, updated_at=utcnow())
        db.add(row)
    return row


@router.patch("/leads/by-key/{lead_key}/state")
def set_state(
    lead_key: str, body: StateIn, principal: Annotated[Principal, require(Action.TRIAGE)], db: WriteDB
) -> LeadStateOut:
    _known_lead(db, lead_key, principal)
    row = _state(db, principal, lead_key)
    if body.assignee_id is not None or body.clear_assignee:
        if not allowed(principal.role, Action.LEAD_ASSIGN):
            raise Problem(403, "forbidden", "only lead analysts can assign leads")
        if body.assignee_id is not None and db.get(User, body.assignee_id) is None:
            raise Problem(422, "validation", "no such user")
        row.assignee_id = None if body.clear_assignee else body.assignee_id
    if body.status is not None:
        row.status = body.status
        row.snooze_until = body.snooze_until if body.status == "SNOOZED" else None
    row.changed_since_review = False
    row.updated_by, row.updated_at = principal.user.id, utcnow()
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="lead.status",
        target_kind="lead",
        target_ref=lead_key,
        payload={"status": row.status, "assignee": row.assignee_id, "private": principal.role == Role.DEMO},
    )
    db.commit()
    return LeadStateOut.model_validate(row)


@router.post("/leads/by-key/{lead_key}/feedback", status_code=201)
def give_feedback(
    lead_key: str, body: FeedbackIn, principal: Annotated[Principal, require(Action.TRIAGE)], db: WriteDB
) -> FeedbackOut:
    _known_lead(db, lead_key, principal)
    run = db.get(Run, body.run_id)
    if run is None:
        raise Problem(404, "not_found", "no such run")
    if body.verdict == "dismiss" and body.reason_code is None:
        raise Problem(422, "validation", "dismissing a lead needs a reason")
    row = Feedback(
        id=new_id("fb"),
        lead_key=state_key(principal, lead_key),
        run_id=run.id,
        user_id=principal.user.id,
        verdict=body.verdict,
        reason_code=body.reason_code,
        note=(body.note or None),
        created_at=utcnow(),
    )
    db.add(row)
    state = _state(db, principal, lead_key)
    state.status, state.changed_since_review = _VERDICT_STATUS[body.verdict], False
    state.updated_by, state.updated_at = principal.user.id, utcnow()
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="lead.feedback",
        target_kind="lead",
        target_ref=lead_key,
        payload={
            "verdict": body.verdict,
            "reason": body.reason_code,
            "run_id": run.id,
            "private": principal.role == Role.DEMO,
        },
    )
    db.commit()
    return FeedbackOut.model_validate(row)


@router.get("/leads/by-key/{lead_key}/feedback")
def list_feedback(
    lead_key: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB
) -> list[FeedbackOut]:  # bounded: at most 100 recent entries
    key = state_key(principal, lead_key)
    rows = db.scalars(
        select(Feedback).where(Feedback.lead_key == key).order_by(Feedback.created_at.desc()).limit(100)
    )
    return [FeedbackOut.model_validate(r) for r in rows]
