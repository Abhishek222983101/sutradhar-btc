"""Ingestion: exact normalisation, every rejection rule, conflict quarantine, dedupe, X-ray, immutability."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from conftest import A_IN, A_PK, A_TR, row, txid

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_schemas.enums import ObservationModel


def _run(write_csv, tmp_path: Path, rows: list[dict[str, str]]):
    return ingest([write_csv(rows)], CANONICAL_CSV, tmp_path / "ds", "ds_test")


def _q(result, sql: str):
    con = duckdb.connect(str(result.path / "dataset.duckdb"), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_valid_rows_normalise_exactly(write_csv, tmp_path: Path) -> None:
    result = _run(write_csv, tmp_path, [row(), row(src_ip="198.51.100.24", timestamp="2026-08-21T19:44:03Z")])
    assert _q(result, "SELECT n_in, n_out, in_sats, out_sats, fee_sats, fee_src, n_obs FROM tx") == [
        (1, 2, 42_000_000, 41_950_000, 50_000, "provided", 2)
    ]
    assert _q(result, "SELECT address, sats, script_type FROM txout ORDER BY idx") == [
        (A_TR, 3_100_000, "p2tr"),
        (A_PK, 38_850_000, "p2pkh"),
    ]
    assert _q(result, "SELECT ts_us, src_ip, dst_port, geo_src, asn_src FROM obs ORDER BY obs_i")[0] == (
        1_787_341_442_113_204,
        "198.51.100.23",
        8333,
        "IN",
        55836,
    )


def test_timestamp_formats(write_csv, tmp_path: Path) -> None:
    rows = [
        row(txid=txid(1), timestamp="2026-08-21T19:44:02.113204Z"),
        row(txid=txid(2), timestamp="2026-08-22T01:14:02.113204+05:30"),  # same instant in IST
        row(txid=txid(3), timestamp="1787341442113"),  # epoch milliseconds
        row(txid=txid(4), timestamp="1787341442"),  # epoch seconds
    ]
    result = _run(write_csv, tmp_path, rows)
    got = dict(_q(result, "SELECT txid, ts_us FROM obs"))
    assert got[txid(1)] == got[txid(2)] == 1_787_341_442_113_204
    assert got[txid(3)] == 1_787_341_442_113_000
    assert got[txid(4)] == 1_787_341_442_000_000


@pytest.mark.parametrize(
    ("override", "rule"),
    [
        ({"txid": "xyz"}, "V01"),
        ({"src_ip": "999.1.1.1"}, "V02"),
        ({"src_port": "70000"}, "V03"),
        ({"timestamp": "yesterday"}, "V04"),
        ({"timestamp": "2001-01-01T00:00:00Z"}, "V04"),
        ({"input_amounts": "[0.42,0.1]"}, "V05"),
        ({"output_amounts": "[0.031,abc]"}, "V06"),
        ({"output_addresses": "[]", "output_amounts": "[]"}, "V07"),
        ({"output_amounts": "[0.5,0.3885]"}, "V08"),
        ({"output_addresses": f'["=cmd|calc!A0","{A_PK}"]'}, "V12"),
    ],
)
def test_rejection_rules(write_csv, tmp_path: Path, override: dict[str, str], rule: str) -> None:
    good = row(txid=txid(99))
    result = _run(write_csv, tmp_path, [good, row(**override)])
    rules = {r[0] for r in _q(result, "SELECT rule FROM rejects")}
    assert rule in rules
    assert result.capability.txs >= 1  # the good row survives


def test_conflicting_txid_quarantined(write_csv, tmp_path: Path) -> None:
    result = _run(write_csv, tmp_path, [row(), row(output_amounts="[0.032,0.3875]")])
    assert _q(result, "SELECT txid, rule FROM quarantine") == [(txid(1), "V10")]
    assert _q(result, "SELECT count(*) FROM tx") == [(0,)]
    assert _q(result, "SELECT count(*) FROM obs") == [(0,)]


def test_exact_duplicates_removed(write_csv, tmp_path: Path) -> None:
    result = _run(write_csv, tmp_path, [row(), row(), row(src_ip="198.51.100.99")])
    assert _q(result, "SELECT count(*) FROM obs") == [(2,)]
    assert result.capability.quality["duplicates"] == 1


def test_chain_only_rows(write_csv, tmp_path: Path) -> None:
    result = _run(write_csv, tmp_path, [row(src_ip="", dst_ip="", src_port="", dst_port="")])
    assert result.capability.network.observation_model == ObservationModel.NONE
    assert "E10" not in result.capability.enabled_stages


def test_dataset_is_immutable(write_csv, tmp_path: Path) -> None:
    result = _run(write_csv, tmp_path, [row()])
    assert not (result.path / "dataset.duckdb").stat().st_mode & 0o222
    with pytest.raises(FileExistsError):
        ingest([write_csv([row()], "again.csv")], CANONICAL_CSV, tmp_path / "ds", "ds_test")


def test_manifest_records_digests(write_csv, tmp_path: Path) -> None:
    result = _run(write_csv, tmp_path, [row()])
    manifest = json.loads((result.path / "manifest.json").read_text())
    assert manifest["profile_ref"] == "canonical-v1@1"
    assert len(manifest["raw_digest"]) == len(manifest["normalised_digest"]) == 64


def test_same_content_same_normalised_digest(write_csv, tmp_path: Path) -> None:
    a = ingest([write_csv([row()], "a.csv")], CANONICAL_CSV, tmp_path / "a", "ds_a")
    b = ingest([write_csv([row()], "b.csv")], CANONICAL_CSV, tmp_path / "b", "ds_b")
    assert a.manifest.normalised_digest == b.manifest.normalised_digest


@pytest.mark.security
def test_undecodable_file_is_a_clean_reader_error(tmp_path: Path) -> None:
    from sutradhar_engine.ingest.readers import ReaderError

    path = tmp_path / "broken.csv"
    path.write_bytes(b'timestamp,txid\n"2026-01-01,unterminated\n' + b"\xff\xfe" * 10)
    with pytest.raises(ReaderError, match=r"cannot read broken\.csv"):
        ingest([path], CANONICAL_CSV, tmp_path / "ds", "ds_broken")


@pytest.mark.security
def test_missing_required_column_is_named(tmp_path: Path) -> None:
    from sutradhar_engine.ingest.mapping import MappingError

    path = tmp_path / "partial.csv"
    path.write_text("timestamp,txid\n2026-01-01T00:00:00Z," + "a" * 64 + "\n", encoding="utf-8")
    with pytest.raises(MappingError, match="input_addresses"):
        ingest([path], CANONICAL_CSV, tmp_path / "ds", "ds_partial")


@pytest.mark.security
def test_empty_file_gives_an_empty_dataset_with_a_warning(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    result = ingest([path], CANONICAL_CSV, tmp_path / "ds", "ds_empty")
    assert result.capability.rows == 0
    assert any("no usable rows" in w for w in result.capability.warnings)


@pytest.mark.security
def test_injection_shaped_fields_never_reach_the_store(write_csv, tmp_path: Path) -> None:
    hostile = row(txid=txid(7), output_addresses=f'["<script>alert(1)</script>","{A_PK}"]')
    result = _run(write_csv, tmp_path, [row(), hostile])
    stored = [r[0] for r in _q(result, "SELECT address FROM txout UNION ALL SELECT address FROM txin")]
    assert all("<" not in a and "=" not in a for a in stored)
    assert A_IN in stored
