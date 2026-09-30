"""The auto-mapper places renamed columns, refuses when required fields are missing, and its profile ingests."""

from __future__ import annotations

from pathlib import Path

from conftest import A_IN, A_PK, A_TR, txid

from sutradhar_engine.ingest.automap import propose_profile
from sutradhar_engine.ingest.pipeline import ingest


def _renamed(tmp: Path) -> Path:
    path = tmp / "odd.csv"
    path.write_text(
        "Seen At,Tx Hash,Peer IP,Peer Port,Sensor IP,Sensor Port,Inputs,Input Values,Outputs,Output Values\n"
        f'2026-08-02T00:09:38Z,{txid(1)},198.51.100.7,51000,192.0.2.9,8333,"[""{A_IN}""]",[0.1],"[""{A_TR}"",""{A_PK}""]","[0.06,0.0399]"\n',
        encoding="utf-8",
    )
    return path


def test_renamed_columns_are_mapped_and_ingest(tmp_path: Path) -> None:
    path = _renamed(tmp_path)
    header = path.read_text().splitlines()[0].split(",")
    row = path.read_text().splitlines()[1]
    samples = {
        "Tx Hash": [txid(1)],
        "Peer IP": ["198.51.100.7"],
        "Sensor IP": ["192.0.2.9"],
        "Peer Port": ["51000"],
        "Inputs": [f'["{A_IN}"]'],
    }
    result = propose_profile(header, samples)
    assert result.profile is not None, result.notes
    assert result.matched["src_ip"][0] == "Peer IP"
    assert result.matched["dst_ip"][0] == "Sensor IP"
    assert row  # the sample file has one data row
    out = ingest([path], result.profile, tmp_path / "ds", "ds_auto")
    assert out.capability.rows == 1
    assert out.capability.quality["rejects"] == 0


def test_missing_required_fields_are_reported() -> None:
    result = propose_profile(["when", "who"], {})
    assert result.profile is None
    assert "txid" in result.missing_required


def test_wrong_content_is_not_matched() -> None:
    result = propose_profile(["src_ip", "txid"], {"src_ip": ["not-an-ip"], "txid": [txid(1)]})
    assert "src_ip" not in result.matched
