"""Refresh refdata/anon-ranges.txt (known Tor-exit and public-VPN CIDR ranges) and its manifest entry.

Maintainers run this online, review the diff and commit — the product itself never downloads anything (I1),
exactly the same pattern as scripts/fetch_refdata.py for the bundled GeoIP databases.

Sources:
  Tor exit relays  https://check.torproject.org/torbulkexitlist (Tor Project, published for this exact purpose)
  Public VPN CIDRs a maintainer-curated URL list passed via --vpn-list (each line: a URL that returns CIDRs,
                    one per line); omit --vpn-list to refresh Tor exits only.

Usage: uv run python scripts/fetch_anon_ranges.py [--vpn-list URL [URL ...]]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "packages/engine/sutradhar_engine/refdata"
FILE = DEST / "anon-ranges.txt"
MANIFEST = DEST / "manifest.json"
TOR_EXIT_LIST_URL = "https://check.torproject.org/torbulkexitlist"


def _fetch_lines(url: str, timeout: int = 60) -> list[str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - maintainer-run, not runtime
        return response.read().decode("utf-8", errors="ignore").splitlines()


def main(vpn_list_urls: list[str] | None = None) -> None:
    entries: list[str] = [
        '# Known Tor-exit and public-VPN CIDR ranges, one per line, "#" comments allowed.',
        f"# Refreshed {datetime.now(UTC).date().isoformat()} by scripts/fetch_anon_ranges.py.",
    ]
    tor_ips = [ln.strip() for ln in _fetch_lines(TOR_EXIT_LIST_URL) if ln.strip() and not ln.startswith("#")]
    entries.append(f"# Tor exit relays ({len(tor_ips)}) — {TOR_EXIT_LIST_URL}")
    entries.extend(f"{ip}/32" for ip in tor_ips)
    for url in vpn_list_urls or []:
        cidrs = [ln.strip() for ln in _fetch_lines(url) if ln.strip() and not ln.startswith("#")]
        entries.append(f"# Public VPN ranges ({len(cidrs)}) — {url}")
        entries.extend(cidrs)

    text = "\n".join(entries) + "\n"
    FILE.write_text(text, encoding="utf-8")
    data = FILE.read_bytes()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["datasets"] = [d for d in manifest["datasets"] if d["file"] != "anon-ranges.txt"]
    manifest["datasets"].append(
        {
            "file": "anon-ranges.txt",
            "source": f"{TOR_EXIT_LIST_URL}"
            + (f" + {len(vpn_list_urls)} VPN list(s)" if vpn_list_urls else ""),
            "as_of": date.today().strftime("%Y-%m-%d"),
            "license": "Tor Project bulk exit list is published for this purpose; VPN sources vary, review before use",
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} lines to {FILE} ({len(tor_ips)} Tor exits)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vpn-list", nargs="*", default=[], help="URLs returning one CIDR per line each")
    args = parser.parse_args()
    main(args.vpn_list)
