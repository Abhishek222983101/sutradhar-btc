"""Runs (E01 to E19 as a job) and their leads."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from sutradhar_api import audit
from sutradhar_api.access import can_see, scoped
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import AppSettings, ReadDB, WriteDB, require
from sutradhar_api.jobs.queue import enqueue, find_idempotent
from sutradhar_api.models import Dataset, Job, Lead, LeadState, MergeDecision, Run
from sutradhar_api.pagination import Cursor, Limit, Page, cursor_time, decode_cursor, encode_cursor
from sutradhar_api.problems import Problem
from sutradhar_api.routes.datasets import DEMO_MAX_ACTIVE_JOBS
from sutradhar_api.schemas import (
    JobOut,
    LeadDetail,
    LeadOut,
    LeadStateOut,
    MergeDecisionIn,
    MergeDecisionOut,
    RunAccepted,
    RunDetail,
    RunIn,
    RunOut,
)
from sutradhar_engine.settings import EngineSettings
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1", tags=["runs"])
MODEL_VERSIONS = {"lead_ranker": "evidence@0.1"}


def _visible_run(db: Session, run_id: str, principal: Principal) -> Run:
    run = db.get(Run, run_id)
    if run is None or not can_see(run.created_by, principal):
        raise Problem(404, "not_found", "no such run")
    return run


@router.post("/runs", status_code=202)
def start_run(
    body: RunIn,
    principal: Annotated[Principal, require(Action.RUN_START)],
    db: WriteDB,
    settings: AppSettings,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> RunAccepted:
    existing = find_idempotent(db, principal.user.id, idempotency_key)
    if existing is not None:
        run = db.get(Run, existing.payload.get("run_id", "")) if existing.kind == "run" else None
        if run is None:
            raise Problem(
                409, "idempotency_conflict", "this Idempotency-Key was used for a different request"
            )
        return RunAccepted(run=RunOut.model_validate(run), job=JobOut.model_validate(existing))
    dataset = db.get(Dataset, body.dataset_id)
    if dataset is None or not can_see(dataset.created_by, principal):
        raise Problem(404, "not_found", "no such dataset")
    if dataset.status != "normalised":
        raise Problem(
            409, "dataset_not_ready", f"the dataset is {dataset.status}; it must finish ingesting first"
        )
    if settings.is_demo:
        active = db.scalars(
            select(Job.id).where(Job.created_by == principal.user.id, Job.status.in_(("queued", "running")))
        ).all()
        if len(active) >= DEMO_MAX_ACTIVE_JOBS:
            raise Problem(429, "busy", "wait for your current jobs to finish before starting another")
    now = utcnow()
    config = EngineSettings(threads=settings.engine_threads).model_dump(mode="json")
    run = Run(
        id=new_id("run"),
        dataset_id=dataset.id,
        status="queued",
        config=config,
        model_versions=MODEL_VERSIONS,
        refdata_versions={},
        created_by=principal.user.id,
        created_at=now,
    )
    db.add(run)
    db.flush()
    job = enqueue(
        db,
        kind="run",
        payload={"run_id": run.id, "dataset_id": dataset.id, "config": config},
        created_by=principal.user.id,
        idempotency_key=idempotency_key,
    )
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="run.start",
        target_kind="run",
        target_ref=run.id,
        payload={"dataset_id": dataset.id, "normalised_digest": dataset.normalised_digest, "job_id": job.id},
    )
    db.commit()
    return RunAccepted(run=RunOut.model_validate(run), job=JobOut.model_validate(job))


@router.get("/runs")
def list_runs(
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    dataset_id: Annotated[str | None, Query(max_length=80)] = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[RunOut]:
    stmt = scoped(select(Run), Run.created_by, principal)
    if dataset_id:
        stmt = stmt.where(Run.dataset_id == dataset_id)
    after = decode_cursor(cursor, (str, str))
    if after is not None:
        at = cursor_time(after[0])
        stmt = stmt.where(or_(Run.created_at < at, and_(Run.created_at == at, Run.id < after[1])))
    rows = list(db.scalars(stmt.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit + 1)))
    more, rows = len(rows) > limit, rows[:limit]
    next_cursor = encode_cursor([rows[-1].created_at.isoformat(), rows[-1].id]) if more else None
    return Page[RunOut](items=[RunOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/runs/{run_id}")
def get_run(run_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB) -> RunDetail:
    return RunDetail.model_validate(_visible_run(db, run_id, principal))


def _lead_out(lead: Lead, state: LeadState | None, model: type[LeadOut] = LeadOut) -> LeadOut:
    out = model.model_validate(lead)
    out.state = LeadStateOut.model_validate(state) if state is not None else None
    return out


@router.get("/runs/{run_id}/leads")
def list_leads(
    run_id: str,
    *,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    type: Annotated[Literal["ACTOR", "CASHOUT", "CHAIN", "TX", "IP"] | None, Query()] = None,
    grade: Annotated[Literal["A", "B", "C"] | None, Query()] = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[LeadOut]:
    run = _visible_run(db, run_id, principal)
    stmt = (
        select(Lead, LeadState)
        .outerjoin(LeadState, LeadState.lead_key == Lead.lead_key)
        .where(Lead.run_id == run.id)
    )
    if type:
        stmt = stmt.where(Lead.type == type)
    if grade:
        stmt = stmt.where(Lead.grade == grade)
    after = decode_cursor(cursor, (float, str))
    if after is not None:
        priority, lead_id = float(after[0]), after[1]
        stmt = stmt.where(or_(Lead.priority < priority, and_(Lead.priority == priority, Lead.id > lead_id)))
    rows = db.execute(stmt.order_by(Lead.priority.desc(), Lead.id).limit(limit + 1)).all()
    more, rows = len(rows) > limit, rows[:limit]
    next_cursor = encode_cursor([rows[-1][0].priority, rows[-1][0].id]) if more else None
    return Page[LeadOut](items=[_lead_out(lead, state) for lead, state in rows], next_cursor=next_cursor)


@router.get("/leads/{lead_id}")
def get_lead(lead_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB) -> LeadDetail:
    row = db.execute(
        select(Lead, LeadState)
        .outerjoin(LeadState, LeadState.lead_key == Lead.lead_key)
        .where(Lead.id == lead_id)
    ).first()
    if row is None:
        raise Problem(404, "not_found", "no such lead")
    lead, state = row
    _visible_run(db, lead.run_id, principal)
    detail = _lead_out(lead, state, LeadDetail)
    return LeadDetail.model_validate(detail)


@router.get("/eval")
def hero_eval() -> dict[str, Any]:
    """Measured accuracy against hidden ground truth (docs/EVAL.json, produced by `sutradhar evals report`)."""
    import json

    from sutradhar_api.demo_seed import EVAL_JSON

    if not EVAL_JSON.exists():
        raise Problem(404, "not_found", "no evaluation report has been generated")
    return json.loads(EVAL_JSON.read_text(encoding="utf-8"))


@router.get("/leads/{lead_id}/evidence")
def lead_evidence(
    lead_id: str, request: Request, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB
) -> dict[str, Any]:
    """The transactions behind an IP-to-wallet lead: candidate origin IPs with posteriors, and the first sensor
    arrivals, which drive the replay in the console."""
    import duckdb

    lead = db.get(Lead, lead_id)
    if lead is None or lead.subject_kind != "ip_cluster":
        raise Problem(404, "not_found", "no such lead")
    _visible_run(db, lead.run_id, principal)
    run = db.get(Run, lead.run_id)
    ip, cluster_id = lead.subject_ref.split("|", 1)
    root = request.app.state.settings.data_dir
    con = duckdb.connect(str(root / "runs" / lead.run_id / "run.duckdb"), read_only=True)
    try:
        con.execute(
            f"ATTACH '{(root / 'datasets' / run.dataset_id / 'dataset.duckdb').as_posix()}' AS ds (READ_ONLY)"
        )
        txs = con.execute(
            """
            SELECT x.txid, x.in_sats, x.first_seen_us
            FROM ds.tx x WHERE x.txid IN (
              SELECT i.txid FROM ds.txin i JOIN cluster c USING (address) WHERE c.cluster_id = ?
            ) AND x.txid IN (SELECT txid FROM origin WHERE rnk = 1 AND ip = ?)
            ORDER BY x.first_seen_us LIMIT 12
            """,
            [cluster_id, ip],
        ).fetchall()
        out = []
        for txid, sats, first_us in txs:
            cands = con.execute("SELECT ip, p FROM origin WHERE txid = ? ORDER BY rnk", [txid]).fetchall()
            arrivals = con.execute(
                "SELECT src_ip, dst_ip, ts_us FROM ds.obs WHERE txid = ? ORDER BY ts_us LIMIT 14", [txid]
            ).fetchall()
            out.append(
                {
                    "txid": txid,
                    "sats": int(sats),
                    "t0_us": int(first_us),
                    "candidates": [{"ip": c[0], "p": round(float(c[1]), 4)} for c in cands],
                    "arrivals": [
                        {"from": a[0], "sensor": a[1], "dt_ms": round((a[2] - first_us) / 1000, 1)}
                        for a in arrivals
                    ],
                }
            )
        wallet = [
            r[0]
            for r in con.execute(
                "SELECT address FROM cluster WHERE cluster_id = ? ORDER BY 1 LIMIT 30", [cluster_id]
            ).fetchall()
        ]
    finally:
        con.close()
    return {"ip": ip, "cluster_id": cluster_id, "addresses": wallet, "transactions": out}


@router.get("/runs/{run_id}/suggestions")
def merge_suggestions(
    run_id: str,
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 20,
    cursor: Cursor = None,
) -> Page[dict[str, Any]]:
    """Wallet-cluster pairs that may belong to one operator (for an analyst to accept or reject), with reasons."""
    import json

    import duckdb

    run = _visible_run(db, run_id, principal)
    path = request.app.state.settings.data_dir / "runs" / run.id / "run.duckdb"
    if not path.exists():
        return Page[dict[str, Any]](items=[], next_cursor=None)
    after = decode_cursor(cursor, (int,))
    offset = after[0] if after else 0
    con = duckdb.connect(str(path), read_only=True)
    try:
        have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        if "merge_suggestion" not in have:
            return Page[dict[str, Any]](items=[], next_cursor=None)
        rows = con.execute(
            "SELECT a, b, score, reasons FROM merge_suggestion ORDER BY score DESC, a, b LIMIT ? OFFSET ?",
            [limit + 1, offset],
        ).fetchall()
    finally:
        con.close()
    more, rows = len(rows) > limit, rows[:limit]
    items = [{"a": r[0], "b": r[1], "score": r[2], "reasons": json.loads(r[3])} for r in rows]
    return Page[dict[str, Any]](items=items, next_cursor=encode_cursor([offset + limit]) if more else None)


@router.post("/merge-decisions", status_code=201)
def decide_merge(
    body: MergeDecisionIn, principal: Annotated[Principal, require(Action.MERGE_DECIDE)], db: WriteDB
) -> MergeDecisionOut:
    """Lead analysts accept or reject a suggested merge. It is recorded with a reason and audited; the pair is
    stored in sorted order so (a, b) and (b, a) are the same decision. A later decision replaces an earlier one."""
    run = _visible_run(db, body.run_id, principal)
    a, b = sorted((body.a, body.b))
    if a == b:
        raise Problem(422, "validation", "a cluster cannot be merged with itself")
    row = db.scalar(select(MergeDecision).where(MergeDecision.a_ref == a, MergeDecision.b_ref == b))
    if row is None:
        row = MergeDecision(id=new_id("mp"), a_ref=a, b_ref=b, run_id=run.id, user_id=principal.user.id)
        db.add(row)
    row.decision, row.reason, row.run_id, row.user_id, row.created_at = (
        body.decision,
        body.reason,
        run.id,
        principal.user.id,
        utcnow(),
    )
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action=f"merge.{body.decision}",
        target_kind="cluster_pair",
        target_ref=f"{a}|{b}",
        payload={"run_id": run.id, "reason": body.reason},
    )
    db.commit()
    return MergeDecisionOut.model_validate(row)


@router.get("/merge-decisions")
def list_merge_decisions(
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[MergeDecisionOut]:
    stmt = select(MergeDecision)
    after = decode_cursor(cursor, (str, str))
    if after is not None:
        at = cursor_time(after[0])
        stmt = stmt.where(
            or_(
                MergeDecision.created_at < at,
                and_(MergeDecision.created_at == at, MergeDecision.id < after[1]),
            )
        )
    rows = list(
        db.scalars(stmt.order_by(MergeDecision.created_at.desc(), MergeDecision.id.desc()).limit(limit + 1))
    )
    more, rows = len(rows) > limit, rows[:limit]
    next_cursor = encode_cursor([rows[-1].created_at.isoformat(), rows[-1].id]) if more else None
    return Page[MergeDecisionOut](
        items=[MergeDecisionOut.model_validate(r) for r in rows], next_cursor=next_cursor
    )
