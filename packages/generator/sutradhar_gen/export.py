"""Exporters: the dataset the system sees (PS minimum fields + extras) and the ground truth only evals see."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import polars as pl

from sutradhar_gen.economy import Tx
from sutradhar_gen.observe import ObservationLog
from sutradhar_schemas.units import micros_to_iso

CANONICAL_COLUMNS = (
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
)


def btc_text(sats: int) -> str:
    """Shortest exact decimal BTC text for an integer satoshi amount ('0.42', '1', '0.00000546')."""
    whole, frac = divmod(sats, 100_000_000)
    if frac == 0:
        return str(whole)
    return f"{whole}.{frac:08d}".rstrip("0")


def _json_list(items: list[str]) -> str:
    return json.dumps(items, separators=(",", ":"))


def _json_amounts(sats: list[int]) -> str:
    return "[" + ",".join(btc_text(v) for v in sats) + "]"


def tx_fields(tx: Tx) -> dict[str, str]:
    scripts = Counter(u.script for u in tx.inputs) if tx.inputs else Counter(o.script for o in tx.outputs)
    dominant = sorted(scripts.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0]
    return {
        "txid": tx.txid,
        "input_addresses": _json_list([u.address for u in tx.inputs]),
        "input_amounts": _json_amounts([u.sats for u in tx.inputs]),
        "output_addresses": _json_list([o.address for o in tx.outputs]),
        "output_amounts": _json_amounts([o.sats for o in tx.outputs]),
        "fee": btc_text(tx.fee_sats),
        "script_type": str(dominant),
    }


def write_canonical_csv(
    path: Path, txs: list[Tx], log: ObservationLog, geo: dict[str, tuple[str, str]] | None = None
) -> int:
    """One row per observation, ordered by (timestamp, dst, src) so output is byte-stable."""
    geo = geo or {}
    order = sorted(
        range(len(log)),
        key=lambda i: (log.ts_us[i], log.dst_ip[i], log.src_ip[i], log.src_port[i], log.tx_index[i]),
    )
    cache: dict[int, dict[str, str]] = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CANONICAL_COLUMNS)
        for i in order:
            ti = log.tx_index[i]
            fields = cache.get(ti) or cache.setdefault(ti, tx_fields(txs[ti]))
            country, asn = geo.get(log.src_ip[i], ("", ""))
            writer.writerow(
                (
                    micros_to_iso(log.ts_us[i]),
                    log.src_ip[i],
                    log.src_port[i],
                    log.dst_ip[i],
                    log.dst_port[i],
                    fields["txid"],
                    fields["input_addresses"],
                    fields["input_amounts"],
                    fields["output_addresses"],
                    fields["output_amounts"],
                    fields["fee"],
                    fields["script_type"],
                    country,
                    asn,
                )
            )
    return len(order)


def _canonical_records(
    txs: list[Tx], log: ObservationLog, geo: dict[str, tuple[str, str]] | None = None
) -> Iterator[dict[str, Any]]:
    """Same row order and content as `write_canonical_csv`, but as records with real array fields — for the
    non-CSV canonical formats (P2.1's readers already accept all four; only CSV was ever produced by `gen run`)."""
    geo = geo or {}
    order = sorted(
        range(len(log)),
        key=lambda i: (log.ts_us[i], log.dst_ip[i], log.src_ip[i], log.src_port[i], log.tx_index[i]),
    )
    cache: dict[int, Tx] = {}
    for i in order:
        ti = log.tx_index[i]
        tx = cache.get(ti) or cache.setdefault(ti, txs[ti])
        country, asn = geo.get(log.src_ip[i], ("", ""))
        yield {
            "timestamp": micros_to_iso(log.ts_us[i]),
            "src_ip": log.src_ip[i],
            "src_port": log.src_port[i],
            "dst_ip": log.dst_ip[i],
            "dst_port": log.dst_port[i],
            "txid": tx.txid,
            "input_addresses": [u.address for u in tx.inputs],
            "input_amounts": [btc_text(u.sats) for u in tx.inputs],
            "output_addresses": [o.address for o in tx.outputs],
            "output_amounts": [btc_text(o.sats) for o in tx.outputs],
            "fee": tx_fields(tx)["fee"],
            "script_type": tx_fields(tx)["script_type"],
            # JSON null, not "": an empty CSV/XML field normalises to NULL on read, but a JSON/NDJSON "" is a
            # real value and stays a real value — null is what makes all four formats agree.
            "geo_country": country or None,
            "asn": asn or None,
        }


def write_canonical_json(
    path: Path, txs: list[Tx], log: ObservationLog, geo: dict[str, tuple[str, str]] | None = None
) -> int:
    """A single JSON array of records — `canonical-json-v1`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = list(_canonical_records(txs, log, geo))
    path.write_text(json.dumps(records), encoding="utf-8")
    return len(records)


def write_canonical_ndjson(
    path: Path, txs: list[Tx], log: ObservationLog, geo: dict[str, tuple[str, str]] | None = None
) -> int:
    """One JSON object per line, no wrapping array — `canonical-ndjson-v1`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in _canonical_records(txs, log, geo):
            handle.write(json.dumps(record))
            handle.write("\n")
            n += 1
    return n


def _xml_record(record: dict[str, Any]) -> str:
    parts = []
    for key, value in record.items():
        if isinstance(value, list):
            items = "".join(f"<item>{escape(str(v))}</item>" for v in value)
            parts.append(f"<{key}>{items}</{key}>")
        else:
            text = "" if value is None else escape(str(value))
            parts.append(f"<{key}>{text}</{key}>")
    return "<record>" + "".join(parts) + "</record>"


def write_canonical_xml(
    path: Path, txs: list[Tx], log: ObservationLog, geo: dict[str, tuple[str, str]] | None = None
) -> int:
    """`<records><record>...</record>...</records>` — `canonical-xml-v1`; entity-safe (I15), no external entities
    are ever written since every text field goes through `xml.sax.saxutils.escape`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = list(_canonical_records(txs, log, geo))
    body = "".join(_xml_record(r) for r in records)
    path.write_text(f"<records>{body}</records>", encoding="utf-8")
    return len(records)


def write_parquet(path: Path, rows: list[dict[str, Any]], schema: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows, schema=schema, orient="row") if rows else pl.DataFrame(schema=schema)
    frame.write_parquet(path, compression="zstd", statistics=False)
