"""Vendor Swagger UI's two static files so /api/docs works with no network (I1, I11).

The tarball is pinned by version and SHA-512 (the npm `dist.integrity`), so a tampered download fails.
Run: `uv run python scripts/vendor_swagger.py` (re-run only when bumping VERSION and INTEGRITY together).
"""

from __future__ import annotations

import base64
import hashlib
import io
import tarfile
import urllib.request
from pathlib import Path

VERSION = "5.33.0"
INTEGRITY = "sha512-wpdK+m6BU5yj6pmUdMskZVTSWYG4DLglAx3sIhylloY37i8O37IrH+YEpqdXNfpaTGxILRBFzUqLF2jKqbfI7A=="
URL = f"https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-{VERSION}.tgz"
FILES = {"package/swagger-ui-bundle.js", "package/swagger-ui.css", "package/LICENSE"}
OUT = Path(__file__).resolve().parents[1] / "apps/api/sutradhar_api/static/swagger"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as response:
        blob = response.read()
    digest = "sha512-" + base64.b64encode(hashlib.sha512(blob).digest()).decode()
    if digest != INTEGRITY:
        raise SystemExit(f"integrity mismatch for {URL}: {digest}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.name in FILES and member.isfile():
                data = tar.extractfile(member)
                if data is None:
                    raise SystemExit(f"cannot read {member.name}")
                (OUT / Path(member.name).name).write_bytes(data.read())
    (OUT / "VERSION").write_text(f"swagger-ui-dist {VERSION}\n{INTEGRITY}\n", encoding="utf-8")
    print(f"vendored swagger-ui-dist {VERSION} into {OUT}")


if __name__ == "__main__":
    main()
