"""Tamper-evident evidence packs: every file is hashed into the manifest, and the manifest carries an HMAC seal.

Why both: a hash list alone only proves the files match the manifest, and whoever edits a file can edit the manifest
to match. The seal is an HMAC over the canonical manifest keyed with the server's signing key, which a person holding
only the zip does not have, so a doctored manifest fails verification just as a doctored file does.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import zipfile
import zlib
from dataclasses import dataclass, field
from typing import Any

SEAL_ALG = "HMAC-SHA256"
SEAL_PURPOSE = b"sutradhar-evidence-seal-v1\n"
MANIFEST = "manifest.json"


def canonical(manifest: dict[str, Any]) -> bytes:
    body = {k: v for k, v in manifest.items() if k != "seal"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()


def seal(manifest: dict[str, Any], key: str) -> str:
    return hmac.new(key.encode(), SEAL_PURPOSE + canonical(manifest), hashlib.sha256).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_pack(files: dict[str, bytes], manifest: dict[str, Any], key: str) -> bytes:
    """A zip of `files` plus a manifest that lists each file's SHA-256 and is itself sealed."""
    sealed = dict(manifest)
    sealed["files"] = {
        name: {"sha256": sha256_hex(data), "bytes": len(data)} for name, data in sorted(files.items())
    }
    sealed["seal_alg"] = SEAL_ALG
    sealed["seal"] = seal(sealed, key)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(files.items()):
            zf.writestr(name, data)
        zf.writestr(MANIFEST, json.dumps(sealed, indent=2, sort_keys=True))
    return buf.getvalue()


@dataclass
class Verdict:
    ok: bool
    manifest_present: bool
    files_checked: int = 0
    sha256_mismatches: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    unlisted_files: list[str] = field(default_factory=list)
    seal_valid: bool = False
    reason: str = ""
    case_id: str | None = None
    title: str | None = None
    generated_at: str | None = None


def _digest(zf: zipfile.ZipFile, name: str) -> str | None:
    """SHA-256 of one member, or None when the member itself is corrupt (bad CRC, broken stream): that counts as changed."""
    try:
        return sha256_hex(zf.read(name))
    except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, EOFError):
        return None


def verify_pack(data: bytes, key: str) -> Verdict:
    """Check a pack end to end. Never raises on a malformed upload: it returns a verdict that says why not."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return Verdict(False, False, reason="not a zip archive")
    with zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if MANIFEST not in names:
            return Verdict(False, False, files_checked=len(names), reason="manifest.json is missing")
        try:
            manifest = json.loads(zf.read(MANIFEST))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Verdict(False, True, files_checked=len(names), reason="manifest.json is not valid JSON")
        listed = manifest.get("files")
        v = Verdict(
            False,
            True,
            case_id=manifest.get("case_id"),
            title=manifest.get("title"),
            generated_at=manifest.get("generated_at"),
        )
        if not isinstance(listed, dict) or "seal" not in manifest:
            v.files_checked = len(names)
            v.reason = (
                "the manifest carries no file hashes or seal, so nothing in this pack can be vouched for"
            )
            return v
        present = [n for n in names if n != MANIFEST]
        v.files_checked = len(present)
        for name, meta in listed.items():
            if name not in present:
                v.missing_files.append(name)
            elif _digest(zf, name) != (meta or {}).get("sha256"):
                v.sha256_mismatches.append(name)
        v.unlisted_files = sorted(n for n in present if n not in listed)
        v.seal_valid = hmac.compare_digest(str(manifest.get("seal", "")), seal(manifest, key))
        problems = []
        if v.sha256_mismatches:
            problems.append(f"{len(v.sha256_mismatches)} file(s) changed after export")
        if v.missing_files:
            problems.append(f"{len(v.missing_files)} listed file(s) missing")
        if v.unlisted_files:
            problems.append(f"{len(v.unlisted_files)} file(s) added that the manifest does not list")
        if not v.seal_valid:
            problems.append(
                "the manifest seal does not match (manifest edited, or not issued by this server)"
            )
        v.ok = not problems
        v.reason = (
            "; ".join(problems) if problems else "every file matches its recorded hash and the seal is valid"
        )
        return v
