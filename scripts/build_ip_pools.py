"""Build the generator's realistic IP pools from the bundled open GeoIP database (DB-IP Lite, CC BY 4.0).

For each country, sample /24 blocks that the database attributes to that country and record the ASN. The
synthetic world then places its nodes in these blocks, so GeoIP enrichment has something real to resolve.
No traffic is ever sent to these addresses; they are labels in a generated file.
Run: uv run python scripts/build_ip_pools.py
"""

from __future__ import annotations

import ipaddress
import json
import random
from pathlib import Path

import maxminddb

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "packages/engine/sutradhar_engine/refdata"
OUT = ROOT / "packages/generator/sutradhar_gen/ip_pools.json"
WEIGHTS = {
    "IN": 30,
    "US": 14,
    "DE": 8,
    "NL": 7,
    "SG": 6,
    "RU": 6,
    "GB": 5,
    "FR": 4,
    "BR": 4,
    "JP": 4,
    "CN": 4,
    "AE": 3,
    "ID": 3,
    "TR": 2,
}
PER_COUNTRY = 24


def main() -> None:
    country = maxminddb.open_database(str(REF / "dbip-country-lite.mmdb"))
    asn = maxminddb.open_database(str(REF / "dbip-asn-lite.mmdb"))
    blocks: dict[str, list[str]] = {c: [] for c in WEIGHTS}
    for network, record in country:
        cc = (record.get("country") or {}).get("iso_code")
        if cc in blocks and isinstance(network, ipaddress.IPv4Network) and network.prefixlen <= 24:
            blocks[cc].append(str(network))
    rng = random.Random(26146)
    pools: dict[str, list[dict[str, object]]] = {}
    for cc, nets in blocks.items():
        rng.shuffle(nets)
        chosen = []
        for net in nets:
            base = ipaddress.ip_network(net)
            off = rng.randrange(0, max(1, base.num_addresses // 256))
            prefix = ipaddress.ip_address(int(base.network_address) + off * 256)
            record = asn.get(str(prefix + 10))
            if not record or "autonomous_system_number" not in record:
                continue
            chosen.append(
                {"prefix": str(prefix).rsplit(".", 1)[0], "asn": record["autonomous_system_number"]}
            )
            if len(chosen) == PER_COUNTRY:
                break
        pools[cc] = chosen
    OUT.write_text(
        json.dumps({"weights": WEIGHTS, "pools": pools}, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print({cc: len(v) for cc, v in pools.items()})


if __name__ == "__main__":
    main()
