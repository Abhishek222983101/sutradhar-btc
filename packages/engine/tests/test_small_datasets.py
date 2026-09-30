"""Small or unusual datasets must run to completion (never crash a stage) and say what they could not do."""

from __future__ import annotations

from pathlib import Path

import duckdb
from conftest import A_IN, A_PK, A_TR, HEADER, row, txid

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline


def _run(path: Path, tmp: Path):  # type: ignore[no-untyped-def]
    ds = ingest([path], CANONICAL_CSV, tmp / "ds", "ds_small")
    manifest = run_pipeline(ds.path, tmp / "run", "run_small")
    return ds, manifest


def test_single_transaction(write_csv, tmp_path: Path) -> None:
    _, manifest = _run(write_csv([row()]), tmp_path)
    assert manifest.result_digest


def test_chain_only_dataset_skips_network_stages_and_still_ranks(tmp_path: Path) -> None:
    lines = [",".join(HEADER)]
    for i in range(1, 41):
        lines.append(
            f'2026-08-02T00:{i % 60:02d}:00Z,,,,,{txid(i)},"[""{A_IN}""]",[0.4],"[""{A_TR}"",""{A_PK}""]","[0.1,0.2999]",0.0001,p2wpkh,,'
        )
    path = tmp_path / "chain.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ds, manifest = _run(path, tmp_path)
    assert ds.capability.network.observation_model == "none"
    for stage in ("E09", "E11", "E16"):
        assert "skipped" in " ".join(manifest.stages[stage].notes)
    con = duckdb.connect(str(tmp_path / "run" / "run.duckdb"), read_only=True)
    assert con.execute("SELECT count(*) FROM actor_features").fetchone()[0] >= 1
    con.close()
