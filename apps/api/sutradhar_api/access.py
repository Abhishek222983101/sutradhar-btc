"""Row visibility. Demo visitors see the shared demo world (rows created by the system) and their own rows;
every other role sees everything its permissions allow."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from sutradhar_api.auth.permissions import SEE_ALL_JOBS
from sutradhar_api.auth.service import Principal
from sutradhar_schemas.enums import Role


def scoped(stmt: Any, created_by: Any, principal: Principal) -> Any:
    if principal.role == Role.DEMO:
        return stmt.where(or_(created_by == principal.user.id, created_by.is_(None)))
    return stmt


def can_see(created_by: str | None, principal: Principal) -> bool:
    return principal.role != Role.DEMO or created_by in (None, principal.user.id)


def can_see_job(created_by: str | None, principal: Principal) -> bool:
    return principal.role in SEE_ALL_JOBS or created_by == principal.user.id
