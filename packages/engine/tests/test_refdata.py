"""I20: every reference dataset carries source, licence and as-of date, and the files match their checksums."""

from __future__ import annotations

from sutradhar_engine.geoip import lookup, manifest, verify_files


def test_manifest_records_provenance_for_every_file() -> None:
    entries = manifest()["datasets"]
    assert {e["file"] for e in entries} == {"dbip-country-lite.mmdb", "dbip-asn-lite.mmdb"}
    for e in entries:
        assert e["source"].startswith("https://") and e["license"] and e["as_of"] and len(e["sha256"]) == 64


def test_bundled_files_match_their_checksums() -> None:
    assert verify_files() == []


def test_lookup_resolves_public_and_refuses_reserved() -> None:
    assert lookup("8.8.8.8").country == "US"
    reserved = lookup("192.0.2.5")
    assert reserved.country is None and "reserved" in (reserved.note or "")
    assert lookup("not-an-ip").note == "not an IP address"
