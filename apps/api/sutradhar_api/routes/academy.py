"""Academy: judges and analysts try one timed challenge against the live system. Truth never reaches the client."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.academy import ANSWERS, public_challenge, score
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import ReadDB, WriteDB, require
from sutradhar_api.models import AcademyAttempt
from sutradhar_api.pagination import Limit
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import Out
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1/academy", tags=["academy"])


@router.get("/challenges")
def list_challenges(principal: Annotated[Principal, require(Action.ACADEMY_ATTEMPT)]) -> list[dict]:
    c = public_challenge()
    return [
        {"id": c["id"], "title": c["title"], "time_limit_s": c["time_limit_s"], "questions": c["questions"]}
    ]


class AttemptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, str] = Field(max_length=20)
    duration_s: int = Field(ge=0, le=3600)


class AttemptOut(Out):
    id: str
    score: float
    duration_s: int
    created_at: datetime


@router.post("/challenges/{challenge_id}/attempts", status_code=201)
def attempt(
    challenge_id: str,
    body: AttemptIn,
    principal: Annotated[Principal, require(Action.ACADEMY_ATTEMPT)],
    db: WriteDB,
) -> AttemptOut:
    if challenge_id != public_challenge()["id"]:
        raise Problem(404, "not_found", "no such challenge")
    if set(body.answers) - set(ANSWERS):
        raise Problem(422, "validation", "unknown question id in answers")
    result, _ = score(body.answers)
    row = AcademyAttempt(
        id=new_id("scn"),
        challenge_id=challenge_id,
        user_id=principal.user.id,
        answers=body.answers,
        score=result,
        duration_s=body.duration_s,
        created_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="academy.attempt",
        target_kind="academy",
        target_ref=challenge_id,
        payload={"score": result},
    )
    db.commit()
    return AttemptOut.model_validate(row)


@router.get("/leaderboard")
def leaderboard(
    principal: Annotated[Principal, require(Action.ACADEMY_ATTEMPT)], db: ReadDB, limit: Limit = 20
) -> list[dict]:
    rows = (
        db.execute(
            select(AcademyAttempt)
            .order_by(AcademyAttempt.score.desc(), AcademyAttempt.duration_s)
            .limit(min(limit, 20))
        )
        .scalars()
        .all()
    )
    return [
        {
            "user_id": r.user_id,
            "score": r.score,
            "duration_s": r.duration_s,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
