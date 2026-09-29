"""Liveness, readiness, system information and audit-chain verification."""

from __future__ import annotations

import tempfile
from typing import Annotated, Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from sutradhar_api import audit, offline_guard
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import AppSettings, ReadDB, require
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import AuditVerifyOut

router = APIRouter(tags=["system"])


@router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Cheap, touches nothing."""
    return {"status": "ok"}


@router.get("/api/ready")
def ready(request: Request, db: ReadDB, settings: AppSettings) -> dict[str, Any]:
    """Readiness: the database answers, the schema is current and the data directory is writable."""
    checks: dict[str, bool] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    checks["schema"] = bool(getattr(request.app.state, "schema_current", False))
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.data_dir, prefix=".ready-"):
            checks["data_dir"] = True
    except OSError:
        checks["data_dir"] = False
    worker = getattr(request.app.state, "worker", None)
    if settings.embedded_worker:
        checks["worker"] = bool(worker and worker.running.is_set())
    if not all(checks.values()):
        failing = ", ".join(k for k, ok in checks.items() if not ok)
        raise Problem(503, "not_ready", f"not ready: {failing}")
    return {"status": "ready", "checks": checks}


@router.get("/api/v1/system/info")
def system_info(request: Request, settings: AppSettings) -> dict[str, Any]:
    worker = getattr(request.app.state, "worker", None)
    return {
        "name": "Sutradhar",
        "problem_statement": "SIH26146",
        "version": settings.version,
        "git_sha": settings.git_sha,
        "mode": str(settings.app_mode),
        "offline_guard": offline_guard.status(),
        "database": request.app.state.db.dialect,
        "worker": {"embedded": settings.embedded_worker, "running": bool(worker and worker.running.is_set())},
        "limits": {
            "upload_max_mb": settings.upload_cap_bytes // (1024 * 1024),
            "upload_max_rows": settings.demo_upload_max_rows if settings.is_demo else None,
            "upload_ttl_min": settings.demo_upload_ttl_min if settings.is_demo else None,
        },
        "time_utc": utcnow().isoformat(),
    }


@router.get("/api/v1/audit/verify")
def verify_audit(principal: Annotated[Principal, require(Action.AUDIT_VERIFY)], db: ReadDB) -> AuditVerifyOut:
    result = audit.verify(db)
    return AuditVerifyOut(
        ok=result.ok,
        entries=result.entries,
        head=result.head,
        broken_at=result.broken_at,
        reason=result.reason,
    )
