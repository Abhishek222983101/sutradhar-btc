"""Object pages and search: everything an analyst can open from the omnibox or a link.

Actor (wallet cluster), address, transaction and IP dossiers, plus one search box that recognises what was typed. Every
response is bounded (I12) and read from the immutable run store.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from sutradhar_api.auth.permissions import Action
from sutradhar_api.auth.service import Principal
from sutradhar_api.deps import ReadDB, require
from sutradhar_api.models import Lead
from sutradhar_api.problems import Problem
from sutradhar_api.routes.common import has_table, rows, run_store, visible_run
from sutradhar_engine.geoip import AS_OF, SOURCE, lookup
from sutradhar_schemas.contract import ADDRESS_RE, TXID_RE

router = APIRouter(prefix="/api/v1/runs/{run_id}", tags=["objects"])
TX_INPUTS_SQL = (
    "SELECT idx, address, sats, script_type, coalesce((SELECT cluster_id FROM cluster c WHERE c.address = i.address), '') AS cluster_id"
    " FROM ds.txin i WHERE txid = ? ORDER BY idx LIMIT 100"
)
TX_OUTPUTS_SQL = TX_INPUTS_SQL.replace("ds.txin i", "ds.txout o").replace("i.address", "o.address")
_ASN = re.compile(r"^(?:AS)?(\d{1,10})$", re.IGNORECASE)


def _geo(ip: str) -> dict[str, Any]:
    g = lookup(ip)
    return {
        "ip": ip,
        "country": g.country,
        "asn": g.asn,
        "org": g.org,
        "note": g.note,
        "source": SOURCE,
        "as_of": AS_OF,
    }


@router.get("/search")
def search(
    run_id: str,
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> dict[str, Any]:
    """Recognises a transaction id, address, IP, AS number, wallet-group id, or words in a lead title."""
    run = visible_run(db, run_id, principal)
    text = q.strip()
    hits: list[dict[str, Any]] = []
    with run_store(request, run) as con:
        if (
            TXID_RE.fullmatch(text.lower())
            and con.execute("SELECT 1 FROM ds.tx WHERE txid = ?", [text.lower()]).fetchone()
        ):
            hits.append({"kind": "tx", "ref": text.lower(), "label": f"Transaction {text[:12]}…"})
        try:
            ip = str(ipaddress.ip_address(text))
            if con.execute("SELECT 1 FROM d_ip WHERE ip = ?", [ip]).fetchone():
                hits.append({"kind": "ip", "ref": ip, "label": f"IP {ip}"})
        except ValueError:
            pass
        if ADDRESS_RE.fullmatch(text):
            row = con.execute("SELECT cluster_id FROM cluster WHERE address = ?", [text]).fetchone()
            if row:
                hits.append({"kind": "address", "ref": text, "label": f"Address {text[:14]}…"})
                hits.append(
                    {
                        "kind": "actor",
                        "ref": row[0],
                        "label": f"Wallet group of that address ({row[0][:10]}…)",
                    }
                )
        if (m := _ASN.fullmatch(text)) and has_table(con, "ip_geo"):
            n = con.execute("SELECT count(*) FROM ip_geo WHERE asn = ?", [int(m.group(1))]).fetchone()[0]
            if n:
                hits.append({"kind": "asn", "ref": m.group(1), "label": f"AS{m.group(1)} ({n} IP(s))"})
        if len(text) >= 6 and re.fullmatch(r"[A-Za-z0-9]+", text):
            for (cid,) in con.execute(
                "SELECT cluster_id FROM cluster_stats WHERE cluster_id LIKE ? ORDER BY cluster_id LIMIT 5",
                [text + "%"],
            ).fetchall():
                hits.append({"kind": "actor", "ref": cid, "label": f"Wallet group {cid[:10]}…"})
    needle = "%" + text.lower().replace("%", "").replace("_", "") + "%"
    from sqlalchemy import func

    for lead in db.scalars(
        select(Lead)
        .where(Lead.run_id == run.id, func.lower(Lead.title).like(needle))
        .order_by(Lead.priority.desc())
        .limit(8)
    ):
        hits.append({"kind": "lead", "ref": lead.id, "label": lead.title})
    seen, unique = set(), []
    for h in hits:
        key = (h["kind"], h["ref"])
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return {"query": text, "hits": unique[:20]}


@router.get("/actors/{cluster_id}")
def actor(
    run_id: str,
    cluster_id: str,
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
) -> dict[str, Any]:
    run = visible_run(db, run_id, principal)
    with run_store(request, run) as con:
        stats = rows(con, "SELECT * FROM cluster_stats WHERE cluster_id = ?", [cluster_id])
        if not stats:
            raise Problem(404, "not_found", "no such wallet group")
        risk = (
            rows(con, "SELECT taint, hops, ppr, is_seed FROM cluster_risk WHERE cluster_id = ?", [cluster_id])
            if has_table(con, "cluster_risk")
            else []
        )
        service = rows(con, "SELECT kind, score FROM service WHERE cluster_id = ?", [cluster_id])
        victim = rows(con, "SELECT exposure_out FROM victim WHERE cluster_id = ?", [cluster_id])
        addresses = [
            r[0]
            for r in con.execute(
                "SELECT address FROM cluster WHERE cluster_id = ? ORDER BY address LIMIT 200", [cluster_id]
            ).fetchall()
        ]
        timeline = rows(
            con,
            """SELECT strftime(make_timestamp(t.first_seen_us), '%Y-%m-%d') AS day, count(*) AS payments, sum(t.in_sats) AS sats
               FROM ds.tx t WHERE t.txid IN (SELECT i.txid FROM ds.txin i JOIN cluster c USING (address) WHERE c.cluster_id = ?)
               GROUP BY 1 ORDER BY 1 LIMIT 120""",
            [cluster_id],
        )
        partners = rows(
            con,
            """SELECT CASE WHEN src = ? THEN dst ELSE src END AS other, CASE WHEN src = ? THEN 'out' ELSE 'in' END AS direction, sats, n_tx
               FROM flow WHERE src = ? OR dst = ? ORDER BY sats DESC, other LIMIT 15""",
            [cluster_id] * 4,
        )
        services = {r[0] for r in con.execute("SELECT cluster_id FROM service").fetchall()}
        for p in partners:
            p["is_service"] = p["other"] in services
        ips = (
            [
                {**r, **_geo(r["ip"])}
                for r in rows(
                    con,
                    "SELECT ip, n_tx, mean_p FROM actor_ip WHERE cluster_id = ? ORDER BY n_tx DESC, ip LIMIT 10",
                    [cluster_id],
                )
            ]
            if has_table(con, "actor_ip")
            else []
        )
        paths = (
            rows(
                con,
                "SELECT rank, hops, cost, path FROM risk_path WHERE target = ? ORDER BY rank",
                [cluster_id],
            )
            if has_table(con, "risk_path")
            else []
        )
    leads = db.scalars(
        select(Lead)
        .where(Lead.run_id == run.id, Lead.subject_ref.like(f"%{cluster_id}%"))
        .order_by(Lead.priority.desc())
        .limit(10)
    )
    return {
        "cluster_id": cluster_id,
        "stats": stats[0],
        "risk": risk[0] if risk else None,
        "service": service[0] if service else None,
        "victim": victim[0] if victim else None,
        "addresses": addresses,
        "timeline": timeline,
        "partners": partners,
        "ips": ips,
        "paths": paths,
        "leads": [
            {"id": lead.id, "title": lead.title, "type": lead.type, "p": lead.p, "grade": lead.grade}
            for lead in leads
        ],
    }


@router.get("/addresses/{address}")
def address(
    run_id: str,
    address: str,
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
) -> dict[str, Any]:
    if not ADDRESS_RE.fullmatch(address):
        raise Problem(422, "validation", "that does not look like a Bitcoin address")
    run = visible_run(db, run_id, principal)
    with run_store(request, run) as con:
        row = con.execute("SELECT cluster_id FROM cluster WHERE address = ?", [address]).fetchone()
        if row is None:
            raise Problem(404, "not_found", "this address is not in the data")
        script = con.execute(
            "SELECT script_type FROM (SELECT address, script_type FROM ds.txout UNION SELECT address, script_type FROM ds.txin) WHERE address = ? LIMIT 1",
            [address],
        ).fetchone()
        received = rows(
            con,
            "SELECT o.txid, o.sats, t.first_seen_us AS t_us FROM ds.txout o JOIN ds.tx t USING (txid) WHERE o.address = ? ORDER BY t.first_seen_us LIMIT 50",
            [address],
        )
        spent = rows(
            con,
            "SELECT i.txid, i.sats, t.first_seen_us AS t_us FROM ds.txin i JOIN ds.tx t USING (txid) WHERE i.address = ? ORDER BY t.first_seen_us LIMIT 50",
            [address],
        )
        taint = (
            rows(con, "SELECT taint, hops, is_seed, category FROM taint WHERE address = ?", [address])
            if has_table(con, "taint")
            else []
        )
    return {
        "address": address,
        "cluster_id": row[0],
        "script_type": script[0] if script else "unknown",
        "received": received,
        "spent": spent,
        "taint": taint[0] if taint else None,
    }


@router.get("/tx/{txid}")
def transaction(
    run_id: str,
    txid: str,
    request: Request,
    principal: Annotated[Principal, require(Action.VIEW)],
    db: ReadDB,
) -> dict[str, Any]:
    if not TXID_RE.fullmatch(txid):
        raise Problem(422, "validation", "a transaction id is 64 hexadecimal characters")
    run = visible_run(db, run_id, principal)
    with run_store(request, run) as con:
        tx = rows(con, "SELECT * FROM ds.tx WHERE txid = ?", [txid])
        if not tx:
            raise Problem(404, "not_found", "no such transaction")
        ins = rows(con, TX_INPUTS_SQL, [txid])
        outs = rows(con, TX_OUTPUTS_SQL, [txid])
        origin = (
            rows(con, "SELECT ip, p, rnk FROM origin WHERE txid = ? ORDER BY rnk", [txid])
            if has_table(con, "origin")
            else []
        )
        anomaly = (
            con.execute("SELECT score FROM anomaly WHERE txid = ?", [txid]).fetchone()
            if has_table(con, "anomaly")
            else None
        )
        motif = (
            con.execute("SELECT kind FROM motif WHERE txid = ?", [txid]).fetchone()
            if has_table(con, "motif")
            else None
        )
        cj = (
            con.execute("SELECT p FROM coinjoin WHERE txid = ?", [txid]).fetchone()
            if has_table(con, "coinjoin")
            else None
        )
        change = (
            rows(con, "SELECT idx, p FROM change WHERE txid = ? ORDER BY idx", [txid])
            if has_table(con, "change")
            else []
        )
        sightings = con.execute("SELECT count(*) FROM ds.obs WHERE txid = ?", [txid]).fetchone()[0]
    return {
        "tx": tx[0],
        "inputs": ins,
        "outputs": outs,
        "origin": [{**o, **_geo(o["ip"])} for o in origin],
        "anomaly": float(anomaly[0]) if anomaly else None,
        "motif": motif[0] if motif else None,
        "coinjoin_p": float(cj[0]) if cj else None,
        "change": change,
        "sightings": int(sightings),
    }


@router.get("/ips/{ip}")
def ip_page(
    run_id: str, ip: str, request: Request, principal: Annotated[Principal, require(Action.VIEW)], db: ReadDB
) -> dict[str, Any]:
    try:
        ip = str(ipaddress.ip_address(ip))
    except ValueError as exc:
        raise Problem(422, "validation", "that is not an IP address") from exc
    run = visible_run(db, run_id, principal)
    with run_store(request, run) as con:
        if not con.execute("SELECT 1 FROM d_ip WHERE ip = ?", [ip]).fetchone():
            raise Problem(404, "not_found", "this IP is not in the data")
        clusters = (
            rows(
                con,
                "SELECT cluster_id, n_tx, mean_p FROM actor_ip WHERE ip = ? ORDER BY n_tx DESC, cluster_id LIMIT 20",
                [ip],
            )
            if has_table(con, "actor_ip")
            else []
        )
        seen = rows(
            con,
            "SELECT count(*) AS sightings, count(DISTINCT txid) AS txs, min(ts_us) AS first_us, max(ts_us) AS last_us FROM ds.obs WHERE src_ip = ? OR dst_ip = ?",
            [ip, ip],
        )[0]
        as_sensor = con.execute("SELECT count(*) FROM ds.obs WHERE dst_ip = ?", [ip]).fetchone()[0]
    leads = db.scalars(
        select(Lead).where(Lead.run_id == run.id, Lead.subject_kind == "ip", Lead.subject_ref == ip)
    ).all()
    return {
        "geo": _geo(ip),
        "role": "listening sensor" if as_sensor else "announcing peer",
        "seen": seen,
        "wallet_groups": clusters,
        "leads": [{"id": lead.id, "title": lead.title, "p": lead.p, "grade": lead.grade} for lead in leads],
    }
