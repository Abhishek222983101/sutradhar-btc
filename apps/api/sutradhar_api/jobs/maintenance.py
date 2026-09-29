"""I19 — demo uploads are deleted after their TTL; demo visitor accounts are removed a day after their last
session. Audit entries stay: the chain records that the data existed and when it was purged.
"""

from __future__ import annotations

import logging
import shutil
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select, update

from sutradhar_api import audit
from sutradhar_api.config import Settings
from sutradhar_api.db import Database, utcnow
from sutradhar_api.models import (
    AuthSession,
    Dataset,
    DatasetFile,
    Job,
    JobEvent,
    Lead,
    LeadState,
    RefreshToken,
    Run,
    User,
)
from sutradhar_schemas.enums import Role

log = logging.getLogger("sutradhar.maintenance")
VISITOR_RETENTION = timedelta(hours=24)


def _remove_tree(root: Path, relative: str) -> None:
    target = (root / relative).resolve()
    if target.is_relative_to(root.resolve()) and target.exists():
        for path in [target, *target.rglob("*")]:
            path.chmod(0o700 if path.is_dir() else 0o600)
        shutil.rmtree(target)


def purge_dataset(db: Database, settings: Settings, dataset_id: str, *, reason: str) -> None:
    with db.write() as session:
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            return
        run_ids = list(session.scalars(select(Run.id).where(Run.dataset_id == dataset_id)))
        if run_ids:
            session.execute(delete(Lead).where(Lead.run_id.in_(run_ids)))
            session.execute(delete(LeadState).where(LeadState.last_seen_run_id.in_(run_ids)))
            session.execute(update(Run).where(Run.prev_run_id.in_(run_ids)).values(prev_run_id=None))
            session.execute(delete(Run).where(Run.id.in_(run_ids)))
        session.execute(delete(DatasetFile).where(DatasetFile.dataset_id == dataset_id))
        session.delete(dataset)
        audit.append(
            session,
            actor_id=None,
            actor_role=audit.SYSTEM,
            action="dataset.purged",
            target_kind="dataset",
            target_ref=dataset_id,
            payload={"reason": reason, "runs": len(run_ids)},
        )
        session.commit()
    root = settings.data_dir
    for relative in (f"uploads/{dataset_id}", f"datasets/{dataset_id}", *(f"runs/{r}" for r in run_ids)):
        _remove_tree(root, relative)


def _purge_visitors(db: Database) -> int:
    cutoff = utcnow() - VISITOR_RETENTION
    removed = 0
    with db.write() as session:
        candidates = session.scalars(
            select(User.id).where(User.role == Role.DEMO, User.created_at < cutoff).limit(200)
        ).all()
        for user_id in candidates:
            live = session.scalar(
                select(AuthSession.id).where(
                    AuthSession.user_id == user_id, AuthSession.expires_at > utcnow()
                )
            )
            owns_data = session.scalar(select(Dataset.id).where(Dataset.created_by == user_id).limit(1))
            if live or owns_data:
                continue
            session_ids = select(AuthSession.id).where(AuthSession.user_id == user_id)
            session.execute(delete(RefreshToken).where(RefreshToken.session_id.in_(session_ids)))
            session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
            job_ids = select(Job.id).where(Job.created_by == user_id)
            session.execute(delete(JobEvent).where(JobEvent.job_id.in_(job_ids)))
            session.execute(delete(Job).where(Job.created_by == user_id))
            session.execute(update(Run).where(Run.created_by == user_id).values(created_by=None))
            session.execute(delete(User).where(User.id == user_id))
            removed += 1
        session.commit()
    return removed


def purge_expired(db: Database, settings: Settings) -> int:
    with db.read() as session:
        expired = list(
            session.scalars(
                select(Dataset.id)
                .where(Dataset.expires_at.is_not(None), Dataset.expires_at < utcnow())
                .limit(50)
            )
        )
    for dataset_id in expired:
        purge_dataset(db, settings, dataset_id, reason="demo upload TTL")
    visitors = _purge_visitors(db) if settings.is_demo else 0
    if expired or visitors:
        log.info("purged %d expired dataset(s) and %d demo visitor(s)", len(expired), visitors)
    return len(expired)
