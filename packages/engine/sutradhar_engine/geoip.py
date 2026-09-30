"""Offline GeoIP: DB-IP Lite country and ASN databases (CC BY 4.0), bundled in `refdata/`.

Every answer carries its source and as-of date (I20). Reserved or private addresses resolve to no place and say so.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import maxminddb

REFDATA = Path(__file__).parent / "refdata"
SOURCE = "DB-IP Lite (CC BY 4.0), https://db-ip.com"
AS_OF = "2026-09"
ANON_FILE = REFDATA / "anon-ranges.txt"
ANON_SOURCE = "maintainer-refreshed Tor/VPN range list, see refdata/anon-ranges.txt"


@dataclass(frozen=True)
class GeoResult:
    ip: str
    country: str | None
    asn: int | None
    org: str | None
    note: str | None = None


@lru_cache(maxsize=1)
def _readers() -> tuple[maxminddb.Reader, maxminddb.Reader]:
    return (
        maxminddb.open_database(str(REFDATA / "dbip-country-lite.mmdb")),
        maxminddb.open_database(str(REFDATA / "dbip-asn-lite.mmdb")),
    )


@lru_cache(maxsize=1)
def _anon_ranges() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Known Tor-exit / public-VPN CIDR ranges (P2.7): empty until a maintainer runs
    `scripts/fetch_anon_ranges.py` online and commits the refresh — see anon-ranges.txt."""
    if not ANON_FILE.exists():
        return ()
    nets = []
    for line in ANON_FILE.read_text(encoding="utf-8").splitlines():
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        try:
            nets.append(ipaddress.ip_network(text, strict=False))
        except ValueError:
            continue
    return tuple(nets)


def _anon_note(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    for net in _anon_ranges():
        if addr in net:
            return f"known Tor exit or public VPN range ({ANON_SOURCE})"
    return None


def lookup(ip: str) -> GeoResult:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return GeoResult(ip, None, None, None, "not an IP address")
    if not addr.is_global:
        return GeoResult(ip, None, None, None, "reserved or private range: no public location")
    country_db, asn_db = _readers()
    c = country_db.get(str(addr)) or {}
    a = asn_db.get(str(addr)) or {}
    iso = (c.get("country") or {}).get("iso_code")
    return GeoResult(
        ip, iso, a.get("autonomous_system_number"), a.get("autonomous_system_organization"), _anon_note(addr)
    )


def manifest() -> dict:
    """Provenance of every bundled reference dataset (I20): source, licence, as-of date, checksum."""
    import json

    return json.loads((REFDATA / "manifest.json").read_text(encoding="utf-8"))


def verify_files() -> list[str]:
    """Names of bundled files whose checksum no longer matches the manifest (empty list means intact)."""
    import hashlib

    return [
        e["file"]
        for e in manifest()["datasets"]
        if hashlib.sha256((REFDATA / e["file"]).read_bytes()).hexdigest() != e["sha256"]
    ]
