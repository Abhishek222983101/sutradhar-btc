"""I20: every reference dataset carries source, licence and as-of date, and the files match their checksums."""

from __future__ import annotations

from sutradhar_engine.geoip import lookup, manifest, verify_files


def test_manifest_records_provenance_for_every_file() -> None:
    entries = manifest()["datasets"]
    assert {e["file"] for e in entries} == {"dbip-country-lite.mmdb", "dbip-asn-lite.mmdb", "anon-ranges.txt"}
    for e in entries:
        assert e["source"] and e["license"] and e["as_of"] and len(e["sha256"]) == 64


def test_bundled_files_match_their_checksums() -> None:
    assert verify_files() == []


def test_lookup_resolves_public_and_refuses_reserved() -> None:
    assert lookup("8.8.8.8").country == "US"
    reserved = lookup("192.0.2.5")
    assert reserved.country is None and "reserved" in (reserved.note or "")
    assert lookup("not-an-ip").note == "not an IP address"


def test_anon_ranges_is_empty_until_a_maintainer_refreshes_it() -> None:
    """P2.7: the file ships empty (I1 — the product never fetches anything at runtime); a normal public IP
    must not be flagged just because the list is empty."""
    assert lookup("8.8.8.8").note is None


def test_anon_ranges_flags_a_matching_ip(tmp_path, monkeypatch) -> None:
    from sutradhar_engine import geoip

    custom = tmp_path / "anon-ranges.txt"
    custom.write_text("# test\n1.2.3.0/24\n", encoding="utf-8")
    monkeypatch.setattr(geoip, "ANON_FILE", custom)
    geoip._anon_ranges.cache_clear()
    try:
        result = geoip.lookup("1.2.3.42")
        assert result.note is not None and "Tor" in result.note
        assert geoip.lookup("8.8.8.8").note is None
    finally:
        geoip._anon_ranges.cache_clear()
