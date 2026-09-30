"""E08 gives injected outliers a high anomaly score."""

from __future__ import annotations

from pathlib import Path

import duckdb
from conftest import A_IN, A_PK, A_TR, row, txid

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline


def test_anomaly_scores_injected_outliers_high(write_csv, tmp_path: Path) -> None:
    rows = [row(txid=txid(i), output_amounts=f"[0.0{3 + i % 3},0.3{i % 7}]") for i in range(1, 61)]
    outputs = ",".join(f'"{A_TR}"' for _ in range(40))
    amounts = ",".join("0.05" for _ in range(40))
    rows.append(
        row(
            txid=txid(999),
            input_amounts="[250.0]",
            output_addresses=f"[{outputs}]",
            output_amounts=f"[{amounts}]",
        )
    )
    ds = ingest([write_csv(rows)], CANONICAL_CSV, tmp_path / "ds", "ds_anom").path
    run_pipeline(ds, tmp_path / "run", "run_anom")
    con = duckdb.connect(str(tmp_path / "run" / "run.duckdb"), read_only=True)
    score = con.execute("SELECT score FROM anomaly WHERE txid = ?", [txid(999)]).fetchone()[0]
    typical = con.execute("SELECT median(score) FROM anomaly").fetchone()[0]
    con.close()
    assert score >= 0.97 and typical < 0.6
    _ = (A_IN, A_PK)
