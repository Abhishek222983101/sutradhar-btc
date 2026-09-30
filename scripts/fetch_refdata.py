"""Refresh the bundled GeoIP databases (DB-IP Lite, CC BY 4.0) and rewrite refdata/manifest.json.

Maintainers run this online, review the diff and commit. The product itself never downloads anything (I1).
Usage: uv run python scripts/fetch_refdata.py [YYYY-MM]
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "packages/engine/sutradhar_engine/refdata"
SOURCES = {"dbip-country-lite.mmdb": "country", "dbip-asn-lite.mmdb": "asn"}
LICENSE = "CC BY 4.0 (attribution: IP Geolocation by DB-IP, https://db-ip.com)"


def main(month: str | None = None) -> None:
    month = month or date.today().strftime("%Y-%m")
    entries = []
    for name, kind in SOURCES.items():
        url = f"https://download.db-ip.com/free/dbip-{kind}-lite-{month}.mmdb.gz"
        with tempfile.NamedTemporaryFile(suffix=".gz") as tmp:
            with urllib.request.urlopen(url, timeout=120) as response:
                shutil.copyfileobj(response, tmp)
            tmp.flush()
            with gzip.open(tmp.name) as handle:
                data = handle.read()
        if len(data) < 1_000_000:
            raise SystemExit(f"{url}: suspiciously small download")
        (DEST / name).write_bytes(data)
        entries.append(
            {
                "file": name,
                "source": url,
                "as_of": month,
                "license": LICENSE,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    (DEST / "manifest.json").write_text(json.dumps({"datasets": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"refreshed {len(entries)} databases for {month}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
