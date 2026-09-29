"""The store DDL creates cleanly; money and time are BIGINT (I9, I10)."""

from __future__ import annotations

import duckdb

from sutradhar_engine.store.ddl import DATASET_DDL, ENVELOPE_COLUMNS, RUN_BASE_DDL


def _columns(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], str]:
    rows = con.execute("SELECT table_name, column_name, data_type FROM information_schema.columns").fetchall()
    return {(table, column): dtype for table, column, dtype in rows}


def test_dataset_and_run_ddl_execute() -> None:
    con = duckdb.connect()
    con.execute(DATASET_DDL)
    con.execute(RUN_BASE_DDL)
    tables = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    assert {
        "obs",
        "tx",
        "txin",
        "txout",
        "rejects",
        "quarantine",
        "dataset_meta",
        "d_tx",
        "d_addr",
        "d_ip",
        "run_meta",
    } <= tables


def test_money_and_time_columns_are_bigint() -> None:
    con = duckdb.connect()
    con.execute(DATASET_DDL)
    cols = _columns(con)
    for (table, column), dtype in cols.items():
        if column.endswith("sats") or column.endswith("_us"):
            assert dtype == "BIGINT", f"{table}.{column} is {dtype}"


def test_envelope_columns_enforce_confidence_range() -> None:
    con = duckdb.connect()
    con.execute(f"CREATE TABLE edge_probe (a INTEGER, {ENVELOPE_COLUMNS})")
    con.execute("INSERT INTO edge_probe VALUES (1, 'cioh', 1.0, '{}', 'rules@1', 'run_x')")
    try:
        con.execute("INSERT INTO edge_probe VALUES (2, 'cioh', 1.5, '{}', 'rules@1', 'run_x')")
        raised = False
    except duckdb.ConstraintException:
        raised = True
    assert raised, "confidence outside [0, 1] must be rejected"
