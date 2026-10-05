"""Capture the hero dataset's read-only API answers into apps/web/public/snapshot/hero.json.

The demo API sleeps on a free host. The web app shows this snapshot, clearly labelled, while the live server wakes,
so a visitor never meets an empty page. Re-run after rebuilding the hero world:
    uv run python scripts/build_web_snapshot.py [https://sutradhar-btc-api.onrender.com]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://sutradhar-btc-api.onrender.com").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "apps/web/public/snapshot/hero.json"
RUN = "run_hero"
GUIDE_ADDRESS = "bc1q64weeskl8vkre5urxq24yfpp2xtf9xpjzlmskq"


def call(path: str, token: str | None = None, data: bytes | None = None) -> object | None:
    if not BASE.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise SystemExit("the API base must be https (or localhost)")
    req = urllib.request.Request(BASE + path, data=data, method="POST" if data is not None else "GET")  # noqa: S310
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 - scheme checked above
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            if exc.code < 500:  # a real 4xx (for example 404 for a lead kind without evidence) is an answer
                return None
        except urllib.error.URLError:
            pass
        time.sleep(3 * (attempt + 1))  # the free host answers 5xx while it wakes or is busy
    return None


def main() -> None:
    token = call("/api/v1/auth/demo", data=b"")["access_token"]  # type: ignore[index]
    paths: dict[str, object] = {}

    def grab(path: str) -> object | None:
        value = call(path, token)
        if value is not None:
            paths[path] = value
        return value

    for p in (
        "/api/v1/eval",
        "/api/v1/models",
        "/api/v1/settings",
        f"/api/v1/runs/{RUN}",
        "/api/v1/datasets/ds_hero",
        "/api/v1/datasets/ds_hero/rejects?limit=20",
        f"/api/v1/runs/{RUN}/suggestions?limit=100",
        f"/api/v1/runs/{RUN}/suggestions?limit=6",
    ):
        grab(p)
    leads = grab(f"/api/v1/runs/{RUN}/leads?limit=100")["items"]  # type: ignore[index]
    clusters: set[str] = set()
    for lead in leads:
        lid = lead["id"]
        grab(f"/api/v1/leads/{lid}/explanation")
        if lead["subject_kind"] in ("cluster", "ip", "cashout"):
            grab(f"/api/v1/leads/{lid}/evidence")
        if lead["subject_kind"] == "cluster":
            clusters.add(lead["subject_ref"])
        if lead["subject_kind"] == "cashout":
            clusters.add(lead["subject_ref"].split("|")[0])
        if lead["subject_kind"] == "tx":
            grab(f"/api/v1/runs/{RUN}/tx/{lead['subject_ref']}")
        if lead["subject_kind"] == "ip":
            grab(f"/api/v1/runs/{RUN}/ips/{lead['subject_ref']}")
    ips: set[str] = set()
    asns: set[int] = set()
    addresses = {GUIDE_ADDRESS}
    for cluster in sorted(clusters):
        actor = grab(f"/api/v1/runs/{RUN}/actors/{cluster}")
        if not actor:
            continue
        addresses.update(actor["addresses"][:2])  # type: ignore[index]
        for row in actor["ips"]:  # type: ignore[index]
            ips.add(row["ip"])
            if row.get("asn"):
                asns.add(int(row["asn"]))
    for ip in sorted(ips):
        page = grab(f"/api/v1/runs/{RUN}/ips/{ip}")
        asn = (page or {}).get("geo", {}).get("asn")  # type: ignore[union-attr]
        if asn:
            asns.add(int(asn))
    for asn in sorted(asns):
        grab(f"/api/v1/runs/{RUN}/asn/{asn}")
    for address in sorted(addresses):
        grab(f"/api/v1/runs/{RUN}/addresses/{address}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "run_id": RUN, "paths": paths},
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(paths)} responses, {OUT.stat().st_size / 1e3:.0f} KB -> {OUT} ({time.strftime('%H:%M:%S')})")


if __name__ == "__main__":
    main()
