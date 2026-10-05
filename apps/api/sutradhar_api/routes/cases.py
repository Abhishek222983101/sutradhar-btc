"""Cases: an analyst's working folder of leads/actors/addresses/tx, with notes and exports.

Export kinds: evidence_pack (zip: manifest + leads json + graphml + readme), graphml, misp (JSON event). Exports run
inline (fast enough not to need a job) and are stored under data/exports/<id>/.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from sutradhar_api import audit
from sutradhar_api.auth.permissions import Action, allowed
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import ReadDB, WriteDB, require
from sutradhar_api.evidence import build_pack, verify_pack
from sutradhar_api.models import Case, CaseItem, CaseNote, Export, Lead, Verification
from sutradhar_api.pagination import Cursor, Limit, Page, decode_cursor, encode_cursor
from sutradhar_api.problems import Problem
from sutradhar_api.routes.common import rows, run_store, visible_run
from sutradhar_api.schemas import Out
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1", tags=["cases"])
ItemKind = Literal["lead", "actor", "address", "tx", "ip", "chain"]
ExportKind = Literal["evidence_pack", "graphml", "misp", "i2csv"]


class CaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=2000)


class CaseOut(Out):
    id: str
    title: str
    status: str
    summary: str | None
    owner_id: str
    created_at: datetime
    closed_at: datetime | None


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_kind: ItemKind
    ref: str = Field(min_length=2, max_length=100)
    run_id: str = Field(min_length=4, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class ItemOut(Out):
    id: str
    item_kind: str
    ref: str
    run_id: str
    note: str | None
    added_at: datetime


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body_md: str = Field(min_length=1, max_length=20000)


class NoteOut(Out):
    id: str
    author_id: str
    body_md: str
    created_at: datetime


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ExportKind = "evidence_pack"


class ExportOut(Out):
    id: str
    kind: str
    status: str
    sha256: str | None
    bytes: int | None
    approved_by: str | None
    created_at: datetime


def _case(db, case_id: str) -> Case:  # type: ignore[no-untyped-def]
    row = db.get(Case, case_id)
    if row is None:
        raise Problem(404, "not_found", "no such case")
    return row


def _can_touch(principal: Principal, case: Case) -> bool:
    return case.owner_id == principal.user.id or principal.role in ("lead", "admin")


@router.get("/cases")
def list_cases(
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[CaseOut]:
    stmt = select(Case).order_by(Case.created_at.desc(), Case.id.desc())
    if principal.role not in ("lead", "admin", "auditor"):
        stmt = stmt.where(Case.owner_id == principal.user.id)
    after = decode_cursor(cursor, (str, str))
    if after:
        from sqlalchemy import and_, or_

        at = datetime.fromisoformat(after[0])
        stmt = stmt.where(or_(Case.created_at < at, and_(Case.created_at == at, Case.id < after[1])))
    r = list(db.scalars(stmt.limit(limit + 1)))
    more, r = len(r) > limit, r[:limit]
    return Page[CaseOut](
        items=[CaseOut.model_validate(x) for x in r],
        next_cursor=encode_cursor([r[-1].created_at.isoformat(), r[-1].id]) if more else None,
    )


@router.post("/cases", status_code=201)
def create_case(
    body: CaseIn, principal: Annotated[Principal, require(Action.CASE_WRITE)], db: WriteDB
) -> CaseOut:
    row = Case(
        id=new_id("case"),
        title=body.title.strip(),
        summary=body.summary,
        owner_id=principal.user.id,
        created_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="case.create",
        target_kind="case",
        target_ref=row.id,
        payload={"title": row.title},
    )
    db.commit()
    return CaseOut.model_validate(row)


@router.get("/cases/{case_id}")
def get_case(case_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB) -> CaseOut:
    return CaseOut.model_validate(_case(db, case_id))


@router.patch("/cases/{case_id}")
def update_case(
    case_id: str,
    principal: Annotated[Principal, require(Action.CASE_WRITE)],
    db: WriteDB,
    status: Literal["open", "closed", "archived"] | None = None,
    summary: str | None = None,
) -> CaseOut:
    case = _case(db, case_id)
    if not _can_touch(principal, case):
        raise Problem(403, "forbidden", "only the case owner or a lead analyst can change it")
    if status == "closed" and not allowed(principal.role, Action.CASE_CLOSE):
        raise Problem(403, "forbidden", "only lead analysts can close a case")
    if status is not None:
        case.status = status
        case.closed_at = utcnow() if status == "closed" else None
    if summary is not None:
        case.summary = summary[:2000]
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="case.update",
        target_kind="case",
        target_ref=case.id,
        payload={"status": case.status},
    )
    db.commit()
    return CaseOut.model_validate(case)


@router.post("/cases/{case_id}/items", status_code=201)
def add_item(
    case_id: str, body: ItemIn, principal: Annotated[Principal, require(Action.CASE_WRITE)], db: WriteDB
) -> ItemOut:
    case = _case(db, case_id)
    if not _can_touch(principal, case):
        raise Problem(403, "forbidden", "only the case owner or a lead analyst can change it")
    visible_run(db, body.run_id, principal)
    existing = db.scalar(
        select(CaseItem).where(
            CaseItem.case_id == case_id,
            CaseItem.item_kind == body.item_kind,
            CaseItem.ref == body.ref,
            CaseItem.run_id == body.run_id,
        )
    )
    if existing:
        return ItemOut.model_validate(existing)
    row = CaseItem(
        id=new_id("cit"),
        case_id=case_id,
        item_kind=body.item_kind,
        ref=body.ref,
        run_id=body.run_id,
        note=body.note,
        added_by=principal.user.id,
        added_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="case.item_add",
        target_kind="case",
        target_ref=case_id,
        payload={"item_kind": body.item_kind, "ref": body.ref},
    )
    db.commit()
    return ItemOut.model_validate(row)


@router.get("/cases/{case_id}/items")
def list_items(
    case_id: str,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 100,
    cursor: Cursor = None,
) -> Page[ItemOut]:
    _case(db, case_id)
    after = decode_cursor(cursor, (str,))
    stmt = select(CaseItem).where(CaseItem.case_id == case_id).order_by(CaseItem.added_at.desc(), CaseItem.id)
    if after:
        stmt = stmt.where(CaseItem.id < after[0])
    r = list(db.scalars(stmt.limit(limit + 1)))
    more, r = len(r) > limit, r[:limit]
    return Page[ItemOut](
        items=[ItemOut.model_validate(x) for x in r], next_cursor=encode_cursor([r[-1].id]) if more else None
    )


@router.delete("/cases/{case_id}/items/{item_id}", status_code=204)
def remove_item(
    case_id: str, item_id: str, principal: Annotated[Principal, require(Action.CASE_WRITE)], db: WriteDB
) -> None:
    case = _case(db, case_id)
    if not _can_touch(principal, case):
        raise Problem(403, "forbidden", "only the case owner or a lead analyst can change it")
    item = db.get(CaseItem, item_id)
    if item is None or item.case_id != case_id:
        raise Problem(404, "not_found", "no such item")
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="case.item_remove",
        target_kind="case",
        target_ref=case_id,
        payload={"item_kind": item.item_kind, "ref": item.ref},
    )
    db.delete(item)  # the audit entry keeps the record; the removal itself is what's audited
    db.commit()


@router.post("/cases/{case_id}/notes", status_code=201)
def add_note(
    case_id: str, body: NoteIn, principal: Annotated[Principal, require(Action.CASE_WRITE)], db: WriteDB
) -> NoteOut:
    case = _case(db, case_id)
    if not _can_touch(principal, case):
        raise Problem(403, "forbidden", "only the case owner or a lead analyst can change it")
    row = CaseNote(
        id=new_id("note"),
        case_id=case_id,
        author_id=principal.user.id,
        body_md=body.body_md,
        created_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="case.note",
        target_kind="case",
        target_ref=case_id,
        payload={},
    )
    db.commit()
    return NoteOut.model_validate(row)


@router.get("/cases/{case_id}/notes")
def list_notes(
    case_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB
) -> list[NoteOut]:
    _case(db, case_id)
    return [
        NoteOut.model_validate(n)
        for n in db.scalars(
            select(CaseNote)
            .where(CaseNote.case_id == case_id)
            .order_by(CaseNote.created_at.desc())
            .limit(200)
        )
    ]


# ── evidence export ──────────────────────────────────────────────────────────────────────────────────────


def _safe_cell(value: Any) -> str:
    """I16: neutralise CSV formula injection — a leading =, +, -, @ gets a guarding leading quote."""
    text = str(value)
    return "'" + text if text and text[0] in "=+-@\t\r" else text


def _item_evidence(con, run, kind: str, ref: str, db) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    if kind in ("lead", "actor"):
        cluster_id = ref
        if kind == "lead":
            lead = db.get(Lead, ref)
            cluster_id = lead.subject_ref if lead and lead.subject_kind == "cluster" else ref
        r = rows(con, "SELECT * FROM cluster_stats WHERE cluster_id = ?", [cluster_id])
        return {"kind": kind, "ref": ref, "cluster_id": cluster_id, "stats": r[0] if r else None}
    if kind == "tx":
        r = rows(con, "SELECT * FROM ds.tx WHERE txid = ?", [ref])
        return {"kind": kind, "ref": ref, "tx": r[0] if r else None}
    if kind == "address":
        r = con.execute("SELECT cluster_id FROM cluster WHERE address = ?", [ref]).fetchone()
        return {"kind": kind, "ref": ref, "cluster_id": r[0] if r else None}
    return {"kind": kind, "ref": ref}


def _build_evidence_pack(
    request: Request, db, case: Case, items: list[CaseItem], principal: Principal
) -> bytes:  # type: ignore[no-untyped-def]
    manifest: dict[str, Any] = {
        "case_id": case.id,
        "title": case.title,
        "generated_at": utcnow().isoformat(),
        "generated_by": principal.user.id,
        "items": [],
    }
    files: dict[str, bytes] = {}
    by_run: dict[str, list[CaseItem]] = {}
    for it in items:
        by_run.setdefault(it.run_id, []).append(it)
    for run_id, run_items in by_run.items():
        run = visible_run(db, run_id, principal)
        with run_store(request, run) as con:
            for it in run_items:
                ev = _item_evidence(con, run, it.item_kind, it.ref, db)
                manifest["items"].append(
                    {"item_id": it.id, "kind": it.item_kind, "ref": it.ref, "note": it.note}
                )
                files[f"evidence/{it.id}_{it.item_kind}.json"] = json.dumps(
                    ev, indent=2, default=str
                ).encode()
    notes = db.scalars(
        select(CaseNote).where(CaseNote.case_id == case.id).order_by(CaseNote.created_at)
    ).all()
    files["notes.md"] = (
        "\n\n---\n\n".join(f"**{n.author_id}** ({n.created_at.isoformat()}):\n\n{n.body_md}" for n in notes)
        or "(no notes)"
    ).encode()
    files["README.txt"] = (
        f'Evidence pack for case {case.id} "{case.title}"\nGenerated {manifest["generated_at"]} by {principal.user.id}\n'
        "Every file is hashed into manifest.json, and the manifest carries an HMAC seal from the issuing server.\n"
        "Check it with the Verify page, or POST the zip to /api/v1/verify.\n"
        "This is synthetic-data evaluation output. All findings are leads for review, not statements about any\n"
        "person's identity or guilt.\n"
    ).encode()
    return build_pack(files, manifest, request.app.state.settings.signing_key)


def _build_graphml(request: Request, db, case: Case, items: list[CaseItem], principal: Principal) -> bytes:  # type: ignore[no-untyped-def]
    import xml.etree.ElementTree as ET

    root = ET.Element("graphml", {"xmlns": "http://graphml.graphdrawing.org/xmlns"})
    graph = ET.SubElement(root, "graph", {"id": case.id, "edgedefault": "directed"})
    seen_nodes: set[str] = set()
    edge_i = 0
    for it in items:
        if it.item_kind not in ("lead", "actor"):
            continue
        run = visible_run(db, it.run_id, principal)
        with run_store(request, run) as con:
            cluster_id = it.ref
            if it.item_kind == "lead":
                lead = db.get(Lead, it.ref)
                cluster_id = lead.subject_ref if lead and lead.subject_kind == "cluster" else it.ref
            if cluster_id not in seen_nodes:
                ET.SubElement(graph, "node", {"id": cluster_id})
                seen_nodes.add(cluster_id)
            for r in rows(
                con,
                "SELECT src, dst, sats FROM flow WHERE src = ? OR dst = ? LIMIT 30",
                [cluster_id, cluster_id],
            ):
                for side in (r["src"], r["dst"]):
                    if side not in seen_nodes:
                        ET.SubElement(graph, "node", {"id": side})
                        seen_nodes.add(side)
                e = ET.SubElement(graph, "edge", {"id": f"e{edge_i}", "source": r["src"], "target": r["dst"]})
                ET.SubElement(e, "data", {"key": "sats"}).text = str(r["sats"])
                edge_i += 1
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root)


def _build_misp(db, case: Case, items: list[CaseItem]) -> bytes:
    attrs = []
    for it in items:
        if it.item_kind == "address":
            attrs.append(
                {"type": "btc-wallet", "category": "Financial fraud", "value": it.ref, "to_ids": True}
            )
        elif it.item_kind == "tx":
            attrs.append({"type": "btc-transaction", "category": "Financial fraud", "value": it.ref})
        elif it.item_kind == "ip":
            attrs.append({"type": "ip-src", "category": "Network activity", "value": it.ref})
    event = {
        "Event": {
            "info": case.title,
            "date": utcnow().date().isoformat(),
            "threat_level_id": "3",
            "analysis": "1",
            "distribution": "0",
            "Attribute": attrs,
            "Tag": [{"name": "sutradhar:synthetic-data"}],
        }
    }
    return json.dumps(event, indent=2).encode()


def _build_i2csv(db, case: Case, items: list[CaseItem]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ITEM_KIND", "REF", "NOTE"])
    for it in items:
        w.writerow([_safe_cell(it.item_kind), _safe_cell(it.ref), _safe_cell(it.note or "")])
    return buf.getvalue().encode()


@router.post("/cases/{case_id}/exports", status_code=202)
def create_export(
    case_id: str,
    body: ExportIn,
    request: Request,
    principal: Annotated[Principal, require(Action.EXPORT_CREATE)],
    db: WriteDB,
) -> ExportOut:
    case = _case(db, case_id)
    if not _can_touch(principal, case):
        raise Problem(403, "forbidden", "only the case owner or a lead analyst can export it")
    items = list(db.scalars(select(CaseItem).where(CaseItem.case_id == case_id)))
    row = Export(
        id=new_id("exp"),
        case_id=case_id,
        kind=body.kind,
        status="queued",
        created_by=principal.user.id,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    try:
        data = {
            "evidence_pack": _build_evidence_pack,
            "graphml": lambda r, d, c, i, p: _build_graphml(r, d, c, i, p),
            "misp": lambda *_: _build_misp(db, case, items),
            "i2csv": lambda *_: _build_i2csv(db, case, items),
        }[body.kind](request, db, case, items, principal)
        out_dir = request.app.state.settings.data_dir / "exports" / row.id
        out_dir.mkdir(parents=True, exist_ok=True)
        ext = {"evidence_pack": "zip", "graphml": "graphml", "misp": "json", "i2csv": "csv"}[body.kind]
        path = out_dir / f"export.{ext}"
        path.write_bytes(data)
        row.status, row.file_path, row.sha256, row.bytes = (
            "ready",
            str(path),
            hashlib.sha256(data).hexdigest(),
            len(data),
        )
        row.manifest = {"items": len(items)}
    except Exception as exc:
        row.status, row.error = "failed", str(exc)[:500]
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="export.create",
        target_kind="export",
        target_ref=row.id,
        payload={"kind": body.kind, "case_id": case_id},
    )
    db.commit()
    return ExportOut.model_validate(row)


@router.get("/exports/{export_id}")
def get_export(
    export_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB
) -> ExportOut:
    row = db.get(Export, export_id)
    if row is None:
        raise Problem(404, "not_found", "no such export")
    return ExportOut.model_validate(row)


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB):  # type: ignore[no-untyped-def]
    from fastapi.responses import FileResponse

    row = db.get(Export, export_id)
    if row is None or row.status != "ready" or not row.file_path:
        raise Problem(404, "not_found", "no such export, or it is not ready")
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="export.download",
        target_kind="export",
        target_ref=row.id,
        payload={},
    )
    db.commit()
    media = {
        "evidence_pack": "application/zip",
        "graphml": "application/xml",
        "misp": "application/json",
        "i2csv": "text/csv",
    }[row.kind]
    return FileResponse(row.file_path, media_type=media, filename=Path(row.file_path).name)


class VerifyOut(BaseModel):
    ok: bool
    files_checked: int
    sha256_mismatches: list[str]
    manifest_present: bool
    seal_valid: bool = False
    missing_files: list[str] = []
    unlisted_files: list[str] = []
    reason: str = ""
    case_id: str | None = None
    title: str | None = None
    generated_at: str | None = None


@router.post("/verify")
async def verify_pack_route(
    request: Request, principal: Annotated[Principal, require(Action.VERIFY)], db: WriteDB
) -> VerifyOut:
    """Upload an evidence-pack zip: every file is re-hashed against the manifest and the manifest seal is checked."""
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise Problem(400, "bad_request", "attach the evidence pack as multipart field 'file'")
    data = await upload.read()  # type: ignore[union-attr]
    if len(data) > 50 * 1024 * 1024:
        raise Problem(413, "too_large", "evidence packs are limited to 50 MB for verification")
    verdict = verify_pack(data, request.app.state.settings.signing_key)
    result = VerifyOut(**asdict(verdict))
    row = Verification(
        id=new_id("ev"),
        file_sha256=hashlib.sha256(data).hexdigest(),
        result=result.model_dump(),
        verified_by=principal.user.id,
        created_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="verify.run",
        target_kind="verification",
        target_ref=row.id,
        payload={"ok": result.ok},
    )
    db.commit()
    return result
