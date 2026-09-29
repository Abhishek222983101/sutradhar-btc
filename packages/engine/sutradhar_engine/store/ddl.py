"""DuckDB DDL for the dataset store and the run store (blueprint §4.6, §4.8).

Money columns are BIGINT satoshis (I9); time columns are BIGINT UTC microseconds (I10). Derived-edge
tables carry the evidence envelope columns (I2); they are added by the stages that own them.
"""

from __future__ import annotations

from typing import Final

DATASET_DDL: Final = """
CREATE TABLE IF NOT EXISTS obs (
    obs_i     BIGINT PRIMARY KEY,
    ts_us     BIGINT  NOT NULL,
    src_ip    VARCHAR,
    src_port  INTEGER,
    dst_ip    VARCHAR,
    dst_port  INTEGER,
    txid      VARCHAR NOT NULL,
    file_id   VARCHAR NOT NULL,
    row_no    BIGINT  NOT NULL,
    geo_src   VARCHAR,
    asn_src   BIGINT
);
CREATE TABLE IF NOT EXISTS tx (
    txid          VARCHAR PRIMARY KEY,
    first_seen_us BIGINT  NOT NULL,
    last_seen_us  BIGINT  NOT NULL,
    n_in          INTEGER NOT NULL,
    n_out         INTEGER NOT NULL,
    in_sats       BIGINT  NOT NULL,
    out_sats      BIGINT  NOT NULL,
    fee_sats      BIGINT  NOT NULL,
    fee_src       VARCHAR NOT NULL CHECK (fee_src IN ('provided', 'computed')),
    is_coinbase   BOOLEAN NOT NULL,
    n_obs         INTEGER NOT NULL,
    block_height  INTEGER,
    vsize         INTEGER,
    locktime      BIGINT,
    version       INTEGER,
    rbf           BOOLEAN
);
CREATE TABLE IF NOT EXISTS txin (
    txid        VARCHAR NOT NULL,
    idx         INTEGER NOT NULL,
    address     VARCHAR NOT NULL,
    sats        BIGINT  NOT NULL,
    script_type VARCHAR NOT NULL,
    prevout     VARCHAR,
    PRIMARY KEY (txid, idx)
);
CREATE TABLE IF NOT EXISTS txout (
    txid        VARCHAR NOT NULL,
    idx         INTEGER NOT NULL,
    address     VARCHAR NOT NULL,
    sats        BIGINT  NOT NULL,
    script_type VARCHAR NOT NULL,
    PRIMARY KEY (txid, idx)
);
CREATE TABLE IF NOT EXISTS rejects (
    file_id VARCHAR NOT NULL,
    row_no  BIGINT  NOT NULL,
    rule    VARCHAR NOT NULL,
    field   VARCHAR,
    value   VARCHAR,
    message VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine (
    txid     VARCHAR NOT NULL,
    rule     VARCHAR NOT NULL,
    variants JSON
);
CREATE TABLE IF NOT EXISTS dataset_meta (
    key   VARCHAR PRIMARY KEY,
    value JSON NOT NULL
);
"""

RUN_BASE_DDL: Final = """
CREATE TABLE IF NOT EXISTS d_tx   (tx_i   INTEGER PRIMARY KEY, txid    VARCHAR NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS d_addr (addr_i INTEGER PRIMARY KEY, address VARCHAR NOT NULL UNIQUE, script_type VARCHAR NOT NULL);
CREATE TABLE IF NOT EXISTS d_ip   (ip_i   INTEGER PRIMARY KEY, ip      VARCHAR NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS run_meta (key VARCHAR PRIMARY KEY, value JSON NOT NULL);
"""

# Columns every derived-edge table must declare (I2). Stages append them to their own DDL.
ENVELOPE_COLUMNS: Final = """
    method        VARCHAR NOT NULL,
    confidence    DOUBLE  NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_refs JSON    NOT NULL,
    model_version VARCHAR NOT NULL,
    run_id        VARCHAR NOT NULL
"""
