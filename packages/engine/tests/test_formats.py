"""CSV, JSON, NDJSON and XML give identical normalised content; XML attacks are refused (I15)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape

import duckdb
import pytest
from conftest import row, txid

from sutradhar_engine.digest import table_digest
from sutradhar_engine.ingest.builtin_profiles import BUILTIN_PROFILES
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.ingest.readers import ReaderError

ARRAYS = ("input_addresses", "input_amounts", "output_addresses", "output_amounts")


def _records() -> list[dict]:
    rows = [row(txid=txid(i), output_amounts="[0.031,0.3885]") for i in range(1, 6)]
    return [{**r, **{k: json.loads(r[k]) for k in ARRAYS}} for r in rows]


def _write(tmp: Path) -> dict[str, Path]:
    recs = _records()
    out = {"canonical-v1": tmp / "t.csv"}
    with out["canonical-v1"].open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows({**r, **{k: json.dumps(r[k]) for k in ARRAYS}} for r in recs)
    out["canonical-json-v1"] = tmp / "t.json"
    out["canonical-json-v1"].write_text(json.dumps(recs))
    out["canonical-ndjson-v1"] = tmp / "t.ndjson"
    out["canonical-ndjson-v1"].write_text("\n".join(json.dumps(r) for r in recs))

    def xml(r: dict) -> str:
        parts = [
            f"<{k}>" + "".join(f"<item>{escape(str(i))}</item>" for i in v) + f"</{k}>"
            if isinstance(v, list)
            else f"<{k}>{escape(str(v))}</{k}>"
            for k, v in r.items()
        ]
        return "<record>" + "".join(parts) + "</record>"

    out["canonical-xml-v1"] = tmp / "t.xml"
    out["canonical-xml-v1"].write_text("<records>" + "".join(xml(r) for r in recs) + "</records>")
    return out


def test_all_formats_give_identical_content(tmp_path: Path) -> None:
    digests = set()
    for name, path in _write(tmp_path).items():
        result = ingest([path], BUILTIN_PROFILES[name], tmp_path / name, f"ds_{name.replace('-', '_')}")
        assert result.capability.quality["rejects"] == 0, name
        con = duckdb.connect(str(result.path / "dataset.duckdb"), read_only=True)
        digests.add(
            (
                table_digest(con, "tx", ["txid"]),
                table_digest(con, "txout", ["txid", "idx"]),
                table_digest(con, "obs", ["obs_i"], exclude=("file_id", "row_no")),
            )
        )
        con.close()
    assert len(digests) == 1


@pytest.mark.security
@pytest.mark.parametrize(
    "payload",
    [
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><records><record><txid>&x;</txid></record></records>',
        '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;">]><records><record><txid>&c;</txid></record></records>',
    ],
    ids=["xxe-file", "billion-laughs"],
)
def test_xxe_payload_rejected(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "evil.xml"
    path.write_text(payload)
    with pytest.raises(ReaderError, match="cannot read evil.xml"):
        ingest([path], BUILTIN_PROFILES["canonical-xml-v1"], tmp_path / "ds", "ds_evil")


@pytest.mark.security
def test_bad_json_is_a_clean_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"not": "an array"}')
    with pytest.raises(ReaderError):
        ingest([path], BUILTIN_PROFILES["canonical-json-v1"], tmp_path / "ds", "ds_bad")
