"""Hand-built CSV fixtures for ingestion tests (engine tests never depend on the generator)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

HEADER = [
    "timestamp",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "txid",
    "input_addresses",
    "input_amounts",
    "output_addresses",
    "output_amounts",
    "fee",
    "script_type",
    "geo_country",
    "asn",
]
A_IN = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
A_TR = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
A_PK = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"


def txid(n: int) -> str:
    return f"{n:064x}"


def row(**overrides: str) -> dict[str, str]:
    base = {
        "timestamp": "2026-08-21T19:44:02.113204Z",
        "src_ip": "198.51.100.23",
        "src_port": "51544",
        "dst_ip": "203.0.113.7",
        "dst_port": "8333",
        "txid": txid(1),
        "input_addresses": f'["{A_IN}"]',
        "input_amounts": "[0.42]",
        "output_addresses": f'["{A_TR}","{A_PK}"]',
        "output_amounts": "[0.031,0.3885]",
        "fee": "0.0005",
        "script_type": "p2wpkh",
        "geo_country": "IN",
        "asn": "AS55836",
    }
    base.update(overrides)
    return base


@pytest.fixture
def write_csv(tmp_path: Path):
    def _write(rows: list[dict[str, str]], name: str = "traffic.csv") -> Path:
        path = tmp_path / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return path

    return _write
