"""Evidence packs are tamper-evident: per-file SHA-256 in the manifest plus an HMAC seal over the manifest.
These run without a database — the pack logic is pure."""

from __future__ import annotations

import io
import json
import zipfile

from sutradhar_api.evidence import MANIFEST, build_pack, verify_pack

KEY = "k" * 48


def _pack() -> bytes:
    return build_pack(
        {"evidence/1_lead.json": b'{"p": 0.97}', "notes.md": b"checked the taint path"},
        {"case_id": "case_1", "title": "Demo case", "generated_at": "2026-10-05T00:00:00Z", "items": []},
        KEY,
    )


def _rewrite(data: bytes, change) -> bytes:  # type: ignore[no-untyped-def]
    src = zipfile.ZipFile(io.BytesIO(data))
    files = {n: src.read(n) for n in src.namelist()}
    change(files)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return out.getvalue()


def test_an_untouched_pack_verifies() -> None:
    v = verify_pack(_pack(), KEY)
    assert v.ok and v.seal_valid and v.files_checked == 2
    assert v.case_id == "case_1" and v.sha256_mismatches == []


def test_changing_one_byte_of_a_file_is_caught() -> None:
    bad = _rewrite(_pack(), lambda f: f.update({"evidence/1_lead.json": b'{"p": 0.01}'}))
    v = verify_pack(bad, KEY)
    assert not v.ok and v.sha256_mismatches == ["evidence/1_lead.json"]


def test_editing_the_manifest_to_match_a_forged_file_still_fails_the_seal() -> None:
    def forge(files: dict[str, bytes]) -> None:
        files["notes.md"] = b"forged"
        m = json.loads(files[MANIFEST])
        import hashlib

        m["files"]["notes.md"]["sha256"] = hashlib.sha256(b"forged").hexdigest()
        files[MANIFEST] = json.dumps(m).encode()

    v = verify_pack(_rewrite(_pack(), forge), KEY)
    assert not v.sha256_mismatches and not v.seal_valid and not v.ok


def test_added_and_removed_files_are_reported() -> None:
    v = verify_pack(_rewrite(_pack(), lambda f: (f.pop("notes.md"), f.update({"extra.txt": b"x"}))), KEY)
    assert v.missing_files == ["notes.md"] and v.unlisted_files == ["extra.txt"] and not v.ok


def test_a_pack_sealed_by_another_server_is_not_vouched_for() -> None:
    assert not verify_pack(_pack(), "z" * 48).ok


def test_garbage_and_hashless_packs_are_refused_not_crashed() -> None:
    assert not verify_pack(b"not a zip", KEY).ok
    legacy = _rewrite(_pack(), lambda f: f.update({MANIFEST: b'{"case_id": "c"}'}))
    v = verify_pack(legacy, KEY)
    assert not v.ok and "no file hashes" in v.reason


def test_a_corrupted_member_is_reported_as_changed_not_a_crash() -> None:
    pack = bytearray(_pack())
    info = zipfile.ZipFile(io.BytesIO(bytes(pack))).getinfo("notes.md")
    pack[info.header_offset + 30 + len(b"notes.md") + 2] ^= 0xFF  # a byte inside the member's stored data
    v = verify_pack(bytes(pack), KEY)
    assert not v.ok and "notes.md" in v.sha256_mismatches
