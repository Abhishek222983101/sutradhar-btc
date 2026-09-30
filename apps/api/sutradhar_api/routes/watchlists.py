"""Watchlists: seed wallets (and IPs) that the risk stages start from. Lead analysts and admins manage them.

Each run takes a frozen snapshot (`seeds.csv` in its folder, its checksum recorded on the run), so a run always
reproduces from the seeds it was started with, whatever happens to the list afterwards.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from sutradhar_api import audit
from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.db import utcnow
from sutradhar_api.deps import ReadDB, WriteDB, require
from sutradhar_api.models import Watchlist, WatchlistItem
from sutradhar_api.pagination import Cursor, Limit, Page, decode_cursor, encode_cursor
from sutradhar_api.problems import Problem
from sutradhar_api.schemas import Out
from sutradhar_schemas.contract import ADDRESS_RE
from sutradhar_schemas.ids import new_id

router = APIRouter(prefix="/api/v1", tags=["watchlists"])
CATEGORIES = ("ransomware", "darknet", "scam", "theft", "sanctioned", "mixer", "other")
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 50_000
Category = Literal["ransomware", "darknet", "scam", "theft", "sanctioned", "mixer", "other"]


class WatchlistIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    kind: Literal["address", "ip"] = "address"


class WatchlistOut(Out):
    id: str
    name: str
    kind: str


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=3, max_length=100)
    category: Category = "other"
    source: str = Field(min_length=2, max_length=120)
    confidence: float = Field(default=0.9, gt=0, le=1)


class ItemOut(Out):
    id: str
    value: str
    category: str
    source: str
    confidence: float


def normalise_value(kind: str, raw: str) -> str:
    """The stored form of a watchlist value; raises ValueError with a plain reason."""
    value = raw.strip()
    if kind == "ip":
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError("not a valid IP address") from None
    if not ADDRESS_RE.fullmatch(value):
        raise ValueError("not a plausible Bitcoin address (14 to 90 letters and digits)")
    return value


def _get(db: Session, watchlist_id: str) -> Watchlist:
    row = db.get(Watchlist, watchlist_id)
    if row is None:
        raise Problem(404, "not_found", "no such watchlist")
    return row


@router.get("/watchlists")
def list_watchlists(
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Page[WatchlistOut]:
    after = decode_cursor(cursor, (str,))
    stmt = select(Watchlist).order_by(Watchlist.id)
    if after:
        stmt = stmt.where(Watchlist.id > after[0])
    rows = list(db.scalars(stmt.limit(limit + 1)))
    more, rows = len(rows) > limit, rows[:limit]
    return Page[WatchlistOut](
        items=[WatchlistOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor([rows[-1].id]) if more else None,
    )


@router.post("/watchlists", status_code=201)
def create_watchlist(
    body: WatchlistIn, principal: Annotated[Principal, require(Action.WATCHLIST_MANAGE)], db: WriteDB
) -> WatchlistOut:
    if db.scalar(select(Watchlist.id).where(Watchlist.name == body.name)):
        raise Problem(409, "exists", "a watchlist with this name already exists")
    row = Watchlist(
        id=new_id("wl"),
        name=body.name.strip(),
        kind=body.kind,
        created_by=principal.user.id,
        created_at=utcnow(),
    )
    db.add(row)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="watchlist.create",
        target_kind="watchlist",
        target_ref=row.id,
        payload={"name": row.name, "kind": row.kind},
    )
    db.commit()
    return WatchlistOut.model_validate(row)


@router.get("/watchlists/{watchlist_id}/items")
def list_items(
    watchlist_id: str,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    limit: Limit = 100,
    cursor: Cursor = None,
) -> Page[ItemOut]:
    _get(db, watchlist_id)
    after = decode_cursor(cursor, (str,))
    stmt = select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id).order_by(WatchlistItem.id)
    if after:
        stmt = stmt.where(WatchlistItem.id > after[0])
    rows = list(db.scalars(stmt.limit(limit + 1)))
    more, rows = len(rows) > limit, rows[:limit]
    return Page[ItemOut](
        items=[ItemOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor([rows[-1].id]) if more else None,
    )


def _upsert(db: Session, wl: Watchlist, body: ItemIn, principal: Principal) -> tuple[WatchlistItem, bool]:
    value = normalise_value(wl.kind, body.value)
    row = db.scalar(
        select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id, WatchlistItem.value == value)
    )
    created = row is None
    if row is None:
        row = WatchlistItem(
            id=new_id("wli"), watchlist_id=wl.id, value=value, added_by=principal.user.id, added_at=utcnow()
        )
        db.add(row)
    row.category, row.source, row.confidence = body.category, body.source.strip(), body.confidence
    return row, created


@router.post("/watchlists/{watchlist_id}/items", status_code=201)
def add_item(
    watchlist_id: str,
    body: ItemIn,
    principal: Annotated[Principal, require(Action.WATCHLIST_MANAGE)],
    db: WriteDB,
) -> ItemOut:
    wl = _get(db, watchlist_id)
    try:
        row, _ = _upsert(db, wl, body, principal)
    except ValueError as exc:
        raise Problem(422, "validation", str(exc)) from exc
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="watchlist.add",
        target_kind="watchlist",
        target_ref=wl.id,
        payload={"value": row.value, "category": row.category},
    )
    db.commit()
    return ItemOut.model_validate(row)


@router.delete("/watchlists/{watchlist_id}/items/{item_id}", status_code=204)
def remove_item(
    watchlist_id: str,
    item_id: str,
    principal: Annotated[Principal, require(Action.WATCHLIST_MANAGE)],
    db: WriteDB,
) -> None:
    item = db.get(WatchlistItem, item_id)
    if item is None or item.watchlist_id != watchlist_id:
        raise Problem(404, "not_found", "no such item")
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="watchlist.remove",
        target_kind="watchlist",
        target_ref=watchlist_id,
        payload={"value": item.value},
    )
    db.delete(item)
    db.commit()


class ImportResult(BaseModel):
    added: int
    updated: int
    rejected: list[dict[str, str | int]]
    rejected_total: int


@router.post("/watchlists/{watchlist_id}/import")
async def import_csv(
    watchlist_id: str,
    principal: Annotated[Principal, require(Action.WATCHLIST_MANAGE)],
    db: WriteDB,
    file: Annotated[
        UploadFile,
        File(description="CSV with a header: value (or address / ip), category, source, confidence"),
    ],
) -> ImportResult:
    """Every row is validated; bad rows are reported by line number and skipped, good rows are saved."""
    wl = _get(db, watchlist_id)
    raw = bytearray()
    while chunk := await file.read(1 << 16):
        raw.extend(chunk)
        if len(raw) > MAX_IMPORT_BYTES:
            raise Problem(
                413, "too_large", f"import files are limited to {MAX_IMPORT_BYTES // (1024 * 1024)} MB"
            )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Problem(400, "bad_encoding", "the file must be UTF-8 text") from None
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower() for f in reader.fieldnames or []}
    key = next((k for k in ("value", "address", "ip") if k in fields), None)
    if key is None:
        raise Problem(400, "bad_header", "the first line must name a column: value, address or ip")
    added = updated = 0
    rejected: list[dict[str, str | int]] = []
    rejected_total = 0
    for line, record in enumerate(reader, start=2):
        if line - 1 > MAX_IMPORT_ROWS:
            raise Problem(413, "too_many_rows", f"imports are limited to {MAX_IMPORT_ROWS} rows")
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in record.items() if k}
        try:
            body = ItemIn.model_validate(
                {
                    "value": row.get(key, ""),
                    "category": row.get("category") or "other",
                    "source": row.get("source") or "import",
                    "confidence": float(row.get("confidence") or 0.9),
                }
            )
            _, created = _upsert(db, wl, body, principal)
        except (ValueError, TypeError) as exc:
            rejected_total += 1
            if len(rejected) < 50:
                rejected.append({"line": line, "reason": str(exc).splitlines()[0][:160]})
            continue
        added, updated = added + created, updated + (not created)
    audit.append(
        db,
        actor_id=principal.user.id,
        actor_role=principal.role,
        action="watchlist.import",
        target_kind="watchlist",
        target_ref=wl.id,
        payload={"added": added, "updated": updated, "rejected": rejected_total},
    )
    db.commit()
    return ImportResult(added=added, updated=updated, rejected=rejected, rejected_total=rejected_total)


# ── snapshot for runs ────────────────────────────────────────────────────────────────────────────────────


def snapshot_for_run(db: Session, run_dir: Path) -> dict[str, object]:
    """Freeze every address seed into `<run_dir>/seeds.csv`; returns {sha256, items} for the run record."""
    rows = db.execute(
        select(WatchlistItem.value, WatchlistItem.category, WatchlistItem.source, WatchlistItem.confidence)
        .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
        .where(Watchlist.kind == "address")
        .order_by(WatchlistItem.value)
    ).all()
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["address", "category", "source", "confidence"])
    for value, category, source, confidence in rows:
        writer.writerow([value, category, source.replace("\n", " ")[:120], f"{confidence:.4f}"])
    data = out.getvalue().encode("utf-8")
    if rows:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "seeds.csv").write_bytes(data)
    return {"sha256": hashlib.sha256(data).hexdigest(), "items": len(rows)}
