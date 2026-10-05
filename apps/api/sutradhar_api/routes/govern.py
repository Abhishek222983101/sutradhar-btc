"""Govern: users, settings, model registry (read-only, from the trained model files), audit access.

Settings are analysis thresholds, editable by admins, audited on every change, with defaults shown alongside.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.security import check_password_policy, hash_password
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import ReadDB, WriteDB, require
from sutradhar_api.models import SettingRow, User
from sutradhar_api.pagination import Cursor, Limit, Page, decode_cursor, encode_cursor
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import Out
from sutradhar_engine.settings import EngineSettings
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1", tags=["govern"])


class UserOut(Out):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(pattern="^(analyst|lead|admin|auditor)$")
    password: str = Field(min_length=12, max_length=256)


@router.get("/users")
def list_users(
    principal: Annotated[Principal, require(Action.ADMIN_MANAGE)],
    db: ReadDB,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[UserOut]:
    after = decode_cursor(cursor, (str,))
    stmt = select(User).where(User.role != "demo").order_by(User.id)
    if after:
        stmt = stmt.where(User.id > after[0])
    rows = list(db.scalars(stmt.limit(limit + 1)))
    more, rows = len(rows) > limit, rows[:limit]
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in rows],
        next_cursor=encode_cursor([rows[-1].id]) if more else None,
    )


@router.post("/users", status_code=201)
def create_user(
    body: UserIn, principal: Annotated[Principal, require(Action.ADMIN_MANAGE)], db: WriteDB
) -> UserOut:
    check_password_policy(body.password)
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise Problem(409, "exists", "a user with this email already exists")
    row = User(
        id=new_id("usr"),
        email=body.email.strip().lower(),
        name=body.name.strip(),
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
        created_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="user.create",
        target_kind="user",
        target_ref=row.id,
        payload={"role": row.role},
    )
    db.commit()
    return UserOut.model_validate(row)


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    principal: Annotated[Principal, require(Action.ADMIN_MANAGE)],
    db: WriteDB,
    role: str | None = None,
    is_active: bool | None = None,
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise Problem(404, "not_found", "no such user")
    if role is not None:
        if role not in ("analyst", "lead", "admin", "auditor"):
            raise Problem(422, "validation", "unknown role")
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="user.role_change",
        target_kind="user",
        target_ref=user.id,
        payload={"role": user.role, "active": user.is_active},
    )
    db.commit()
    return UserOut.model_validate(user)


DEFAULTS = EngineSettings().model_dump(mode="json")


class SettingOut(BaseModel):
    key: str
    value: Any
    default: Any
    changed: bool
    updated_by: str | None
    updated_at: datetime | None


@router.get("/settings")
def get_settings(principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB) -> list[SettingOut]:
    overrides = {r.key: r for r in db.scalars(select(SettingRow))}
    out = []
    for key, default in DEFAULTS.items():
        row = overrides.get(key)
        value = row.value if row else default
        out.append(
            SettingOut(
                key=key,
                value=value,
                default=default,
                changed=row is not None and value != default,
                updated_by=row.updated_by if row else None,
                updated_at=row.updated_at if row else None,
            )
        )
    return out


@router.put("/settings/{key}")
def put_setting(
    key: str,
    principal: Annotated[Principal, require(Action.ADMIN_MANAGE)],
    db: WriteDB,
    value: Annotated[Any, Body(embed=False)],
) -> SettingOut:
    if key not in DEFAULTS:
        raise Problem(404, "not_found", f"no such setting: {key}")
    row = db.get(SettingRow, key)
    if row is None:
        row = SettingRow(key=key, value=value, updated_by=principal.user.id, updated_at=utcnow())
        db.add(row)
    else:
        row.value, row.updated_by, row.updated_at = value, principal.user.id, utcnow()
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="settings.change",
        target_kind="setting",
        target_ref=key,
        payload={"value": value},
    )
    db.commit()
    return SettingOut(
        key=key,
        value=row.value,
        default=DEFAULTS[key],
        changed=row.value != DEFAULTS[key],
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


class ModelOut(BaseModel):
    name: str
    version: str
    status: str
    metrics: dict[str, Any]
    trained_on: dict[str, Any]
    card_md: str


@router.get("/models")
def list_models(principal: Annotated[Principal, require(Action.VIEW)]) -> list[ModelOut]:
    from sutradhar_engine.linear_model import MODELS_DIR

    out = []
    for name, filename in (
        ("lead_ranker", "lead_ranker.meta.json"),
        ("origin", "origin_lr.json"),
        ("change", "change_lr.json"),
        ("coinjoin", "coinjoin_lr.json"),
    ):
        path = MODELS_DIR / filename
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        trained = d.get("trained_on", {})
        card = f"# {name}\n\nVersion: {d['version']}\n\nTrained on {trained.get('rows') or trained.get('actors', '?')} rows/actors.\n\nSee docs/EVAL.md for held-out metrics."
        out.append(
            ModelOut(
                name=name,
                version=d["version"],
                status="active",
                metrics={k: v for k, v in trained.items() if isinstance(v, int | float)},
                trained_on=trained,
                card_md=card,
            )
        )
    return out


@router.get("/audit")
def list_audit(
    principal: Annotated[Principal, require(Action.AUDIT_VIEW)],
    db: ReadDB,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[dict[str, Any]]:
    from sutradhar_api.models import AuditLog

    after = decode_cursor(cursor, (int,))
    stmt = select(AuditLog).order_by(AuditLog.seq.desc())
    if after:
        stmt = stmt.where(AuditLog.seq < after[0])
    rows = list(db.scalars(stmt.limit(limit + 1)))
    more, rows = len(rows) > limit, rows[:limit]
    items = [
        {
            "seq": r.seq,
            "ts": r.ts.isoformat(),
            "actor_id": r.actor_id,
            "actor_role": r.actor_role,
            "action": r.action,
            "target_kind": r.target_kind,
            "target_ref": r.target_ref,
            "payload": r.payload,
        }
        for r in rows
    ]
    return Page[dict[str, Any]](items=items, next_cursor=encode_cursor([rows[-1].seq]) if more else None)
