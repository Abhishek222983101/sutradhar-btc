"""The permission matrix (blueprint §2.4) as data. `require(action)` is the only way a route checks it."""

from __future__ import annotations

from enum import StrEnum

from sutradhar_schemas.enums import Role

A, L, M, U, D = Role.ANALYST, Role.LEAD, Role.ADMIN, Role.AUDITOR, Role.DEMO


class Action(StrEnum):
    VIEW = "view"
    TRIAGE = "triage"
    LEAD_ASSIGN = "lead.assign"
    CASE_WRITE = "case.write"
    CASE_CLOSE = "case.close"
    EXPORT_CREATE = "export.create"
    EXPORT_APPROVE = "export.approve"
    VERIFY = "verify"
    MERGE_DECIDE = "merge.decide"
    WATCHLIST_MANAGE = "watchlist.manage"
    DATASET_UPLOAD = "dataset.upload"
    RUN_START = "run.start"
    JOB_CANCEL = "job.cancel"
    LAB_RUN = "lab.run"
    ACADEMY_ATTEMPT = "academy.attempt"
    MODEL_PROMOTE = "model.promote"
    ADMIN_MANAGE = "admin.manage"
    AUDIT_VIEW = "audit.view"
    AUDIT_VERIFY = "audit.verify"
    DEMO_RESET = "demo.reset"
    SESSION = "session"  # any signed-in user: /me, logout


MATRIX: dict[Action, frozenset[Role]] = {
    Action.VIEW: frozenset({A, L, M, U, D}),
    Action.TRIAGE: frozenset({A, L, D}),
    Action.LEAD_ASSIGN: frozenset({L, M}),
    Action.CASE_WRITE: frozenset({A, L, D}),
    Action.CASE_CLOSE: frozenset({L}),
    Action.EXPORT_CREATE: frozenset({A, L, D}),
    Action.EXPORT_APPROVE: frozenset({L}),
    Action.VERIFY: frozenset({A, L, M, U, D}),
    Action.MERGE_DECIDE: frozenset({L}),
    Action.WATCHLIST_MANAGE: frozenset({L, M}),
    Action.DATASET_UPLOAD: frozenset({A, L, M, D}),
    Action.RUN_START: frozenset({A, L, M, D}),
    Action.JOB_CANCEL: frozenset({A, L, M, D}),  # plus ownership, checked in the route
    Action.LAB_RUN: frozenset({L, M, D}),
    Action.ACADEMY_ATTEMPT: frozenset({A, L, M, U, D}),
    Action.MODEL_PROMOTE: frozenset({M}),
    Action.ADMIN_MANAGE: frozenset({M}),
    Action.AUDIT_VIEW: frozenset({L, M, U}),
    Action.AUDIT_VERIFY: frozenset({L, M, U}),
    Action.DEMO_RESET: frozenset({M}),
    Action.SESSION: frozenset({A, L, M, U, D}),
}

# Roles that may see every user's jobs (others see their own).
SEE_ALL_JOBS = frozenset({L, M, U})


def allowed(role: str, action: Action) -> bool:
    return role in MATRIX[action]


def permissions_for(role: str) -> list[str]:
    return sorted(str(action) for action, roles in MATRIX.items() if role in roles)
