"""Ingest files into a dataset store: `<out>/dataset.duckdb` + `manifest.json` + `xray.json`.

Memory stays bounded: observation batches stream straight into DuckDB; only one text copy of each distinct
transaction content is kept in Python.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from sutradhar_engine.digest import combine, table_digest
from sutradhar_engine.ingest.mapping import apply_profile
from sutradhar_engine.ingest.normalise import (
    ContentError,
    Rejects,
    TxContent,
    normalise_observations,
    parse_content,
    script_types,
)
from sutradhar_engine.ingest.readers import SourceFile, read_batches
from sutradhar_engine.ingest.xray import build_capability
from sutradhar_engine.store.ddl import DATASET_DDL
from sutradhar_schemas.canonical import canonical_json, sha256_file, sha256_json
from sutradhar_schemas.contract import CONTRACT_VERSION
from sutradhar_schemas.evidence import CapabilityProfile, DatasetManifest
from sutradhar_schemas.ids import check_id
from sutradhar_schemas.profile import MappingProfile

Progress = Callable[[str, float, str], None]
_CONTENT_COLS = ("txid", "input_addresses", "input_amounts", "output_addresses", "output_amounts", "fee")


@dataclass(frozen=True, slots=True)
class IngestResult:
    dataset_id: str
    path: Path
    manifest: DatasetManifest
    capability: CapabilityProfile


def _noop(_stage: str, _pct: float, _msg: str) -> None:
    return None


def _resolve_unit(profile: MappingProfile) -> dict[str, Any]:
    # P2.3 adds auto-detection from the data; until then 'auto' means BTC (the canonical export unit).
    unit = "btc" if profile.amount_unit in ("auto", "btc") else "sat"
    return {"decision": unit, "setting": profile.amount_unit}


def _sources(files: Sequence[Path]) -> list[SourceFile]:
    sources = []
    for path in sorted(files, key=lambda p: p.name):
        digest = sha256_file(path)
        sources.append(
            SourceFile(file_id=f"f{digest[:12]}", path=path, sha256=digest, bytes=path.stat().st_size)
        )
    return sources


_VARIANT_PARTS = ("input_addresses", "input_amounts", "output_addresses", "output_amounts")


def _stream_observations(
    con: duckdb.DuckDBPyConnection,
    sources: list[SourceFile],
    profile: MappingProfile,
    rejects: Rejects,
    progress: Progress,
) -> tuple[int, pl.DataFrame]:
    """Read every file in batches: observations go to `obs_stage`, distinct content variants are returned."""
    con.execute(
        "CREATE TEMP TABLE obs_stage (ts_us BIGINT, src_ip VARCHAR, src_port INTEGER, dst_ip VARCHAR, dst_port INTEGER,"
        " txid VARCHAR, file_id VARCHAR, row_no BIGINT, geo_src VARCHAR, asn_src BIGINT)"
    )
    source_rows = 0
    frames: list[pl.DataFrame] = []
    for fi, source in enumerate(sources):
        progress("I01", fi / len(sources), f"reading {source.path.name}")
        for batch in read_batches(source, profile):
            source_rows += batch.height
            mapped = apply_profile(batch, profile)
            obs = normalise_observations(mapped, source.file_id, profile, rejects)
            con.register("obs_batch", obs.to_arrow())
            con.execute("INSERT INTO obs_stage SELECT * FROM obs_batch")
            con.unregister("obs_batch")
            raw_key = pl.concat_str(
                [pl.col(c).list.join("|") for c in _VARIANT_PARTS], separator="#", ignore_nulls=True
            )
            variants = (
                mapped.filter(pl.col("txid").is_in(obs["txid"].unique().implode()))
                .with_columns(pl.lit(source.file_id).alias("file_id"), raw_key.alias("raw_key"))
                .unique(subset=["txid", "raw_key"], keep="first", maintain_order=True)
            )
            frames.append(variants.select([*_CONTENT_COLS, "raw_key", "file_id", "__row_no"]))
    if not frames:
        return source_rows, pl.DataFrame()
    merged = pl.concat(frames).unique(subset=["txid", "raw_key"], keep="first", maintain_order=True)
    return source_rows, merged


def _dedupe_and_index(con: duckdb.DuckDBPyConnection) -> int:
    """V11: drop exact duplicate observations, assign dense `obs_i`, fill per-tx first/last seen. Returns
    the number of duplicates removed."""
    con.execute(
        """
        CREATE TEMP TABLE obs_dedup AS
        SELECT * FROM obs_stage
        WHERE txid IN (SELECT txid FROM tx)
        QUALIFY row_number() OVER (
            PARTITION BY ts_us, src_ip, src_port, dst_ip, dst_port, txid ORDER BY file_id, row_no) = 1
        """
    )
    kept = _count(con, "SELECT count(*) FROM obs_stage WHERE txid IN (SELECT txid FROM tx)")
    deduped = _count(con, "SELECT count(*) FROM obs_dedup")
    con.execute(
        """
        INSERT INTO obs
        SELECT row_number() OVER (ORDER BY ts_us, file_id, row_no) - 1 AS obs_i,
               ts_us, src_ip, src_port, dst_ip, dst_port, txid, file_id, row_no, geo_src, asn_src
        FROM obs_dedup
        """
    )
    con.execute(
        """
        UPDATE tx SET first_seen_us = a.f, last_seen_us = a.l, n_obs = a.n
        FROM (SELECT txid, min(ts_us) f, max(ts_us) l, count(*) n FROM obs GROUP BY txid) a
        WHERE tx.txid = a.txid
        """
    )
    return kept - deduped


def _count(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    row = con.execute(sql).fetchone()
    return 0 if row is None else int(row[0])


def _write_problems(
    con: duckdb.DuckDBPyConnection, rejects: Rejects, quarantine: list[dict[str, str]]
) -> None:
    if rejects.rows:
        con.register("rej", pl.DataFrame(rejects.rows, schema=_REJECT_SCHEMA, orient="row").to_arrow())
        con.execute("INSERT INTO rejects SELECT * FROM rej")
        con.unregister("rej")
    if quarantine:
        frame = pl.DataFrame(quarantine, schema={"txid": str, "rule": str, "variants": str}, orient="row")
        con.register("q", frame.to_arrow())
        con.execute("INSERT INTO quarantine SELECT txid, rule, variants::JSON FROM q")
        con.unregister("q")


def _manifest(
    con: duckdb.DuckDBPyConnection,
    *,
    dataset_id: str,
    sources: list[SourceFile],
    profile: MappingProfile,
    capability: CapabilityProfile,
    counts: dict[str, int],
) -> DatasetManifest:
    normalised = {
        "obs": table_digest(con, "obs", ["obs_i"]),
        "tx": table_digest(con, "tx", ["txid"]),
        "txin": table_digest(con, "txin", ["txid", "idx"]),
        "txout": table_digest(con, "txout", ["txid", "idx"]),
    }
    return DatasetManifest(
        dataset_id=dataset_id,
        files=[
            {"file_id": s.file_id, "filename": s.path.name, "sha256": s.sha256, "bytes": s.bytes}
            for s in sources
        ],
        profile_ref=profile.ref,
        profile_sha256=profile.spec_sha256(),
        raw_digest=sha256_json(
            {"files": [(s.path.name, s.sha256) for s in sources], "profile": profile.spec_sha256()}
        ),
        normalised_digest=combine(normalised),
        contract_version=CONTRACT_VERSION,
        row_counts={**counts, "obs": capability.rows, "tx": capability.txs},
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ingest(
    files: Sequence[Path],
    profile: MappingProfile,
    out_dir: Path,
    dataset_id: str,
    progress: Progress = _noop,
) -> IngestResult:
    check_id(dataset_id, "ds")
    if not files:
        raise ValueError("no input files")
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "dataset.duckdb"
    if db_path.exists():
        raise FileExistsError(f"{db_path} already exists; datasets are immutable")

    sources = _sources(files)
    unit_info = _resolve_unit(profile)
    rejects = Rejects()
    con = duckdb.connect(str(db_path))
    try:
        con.execute(DATASET_DDL)
        source_rows, variants = _stream_observations(con, sources, profile, rejects, progress)

        progress("I03", 0.6, "normalising transactions")
        contents, quarantine = _resolve_contents(variants, str(unit_info["decision"]), rejects)
        _write_tx_tables(con, contents)

        progress("I05", 0.8, "removing duplicates")
        duplicates = _dedupe_and_index(con)
        _write_problems(con, rejects, quarantine)

        progress("I06", 0.9, "profiling")
        capability = build_capability(
            con,
            amount_unit=unit_info,
            rejects=len({(r["file_id"], r["row_no"]) for r in rejects.rows}),
            duplicates=duplicates,
            source_rows=source_rows,
            conflicts=len(quarantine),
        )
        manifest = _manifest(
            con,
            dataset_id=dataset_id,
            sources=sources,
            profile=profile,
            capability=capability,
            counts={
                "source_rows": source_rows,
                "rejects": len(rejects.rows),
                "quarantined_txids": len(quarantine),
            },
        )
        for key, value in (
            ("manifest", manifest.model_dump(mode="json")),
            ("capability", capability.model_dump(mode="json")),
            ("profile", profile.model_dump(mode="json")),
        ):
            con.execute("INSERT INTO dataset_meta VALUES (?, ?)", [key, canonical_json(value).decode()])
        con.execute("CHECKPOINT")
    finally:
        con.close()

    _write_json(out_dir / "manifest.json", manifest.model_dump(mode="json"))
    _write_json(out_dir / "xray.json", capability.model_dump(mode="json"))
    db_path.chmod(0o444)  # datasets are immutable once written
    progress("I06", 1.0, "done")
    return IngestResult(dataset_id, out_dir, manifest, capability)


_REJECT_SCHEMA = {"file_id": str, "row_no": pl.Int64, "rule": str, "field": str, "value": str, "message": str}


def _resolve_contents(
    variants: pl.DataFrame, unit: str, rejects: Rejects
) -> tuple[list[TxContent], list[dict[str, str]]]:
    """Parse each distinct content variant; quarantine txids with conflicting or invalid content."""
    if variants.is_empty():
        return [], []
    by_txid: dict[str, list[dict[str, Any]]] = {}
    for row in variants.iter_rows(named=True):
        by_txid.setdefault(row["txid"], []).append(row)
    contents: list[TxContent] = []
    quarantine: list[dict[str, str]] = []
    for txid in sorted(by_txid):
        rows = by_txid[txid]
        parsed: list[TxContent] = []
        error: ContentError | None = None
        for row in rows:
            try:
                parsed.append(parse_content(txid, row, unit))
            except ContentError as exc:
                error = exc
                rejects.add(
                    row["file_id"],
                    row["__row_no"],
                    exc.rule,
                    field_name=exc.field_name,
                    value=None,
                    message=str(exc),
                )
        if error is not None:
            quarantine.append({"txid": txid, "rule": error.rule, "variants": json.dumps([str(error)])})
            continue
        if len({p.key() for p in parsed}) > 1:
            quarantine.append(
                {"txid": txid, "rule": "V10", "variants": json.dumps([r["raw_key"][:400] for r in rows])}
            )
            for row in rows:
                rejects.add(
                    row["file_id"],
                    row["__row_no"],
                    "V10",
                    field_name="txid",
                    value=txid,
                    message="same txid appears with different contents",
                )
            continue
        contents.append(parsed[0])
    return contents, quarantine


def _write_tx_tables(con: duckdb.DuckDBPyConnection, contents: list[TxContent]) -> None:
    tx_rows, in_rows, out_rows = [], [], []
    for c in contents:
        tx_rows.append(
            {
                "txid": c.txid,
                "first_seen_us": 0,
                "last_seen_us": 0,
                "n_in": len(c.in_sats),
                "n_out": len(c.out_sats),
                "in_sats": sum(c.in_sats),
                "out_sats": sum(c.out_sats),
                "fee_sats": c.fee_sats,
                "fee_src": c.fee_src,
                "is_coinbase": not c.in_sats,
                "n_obs": 0,
            }
        )
        for idx, (addr, sats, script) in enumerate(
            zip(c.in_addresses, c.in_sats, script_types(c.in_addresses), strict=True)
        ):
            in_rows.append({"txid": c.txid, "idx": idx, "address": addr, "sats": sats, "script_type": script})
        for idx, (addr, sats, script) in enumerate(
            zip(c.out_addresses, c.out_sats, script_types(c.out_addresses), strict=True)
        ):
            out_rows.append(
                {"txid": c.txid, "idx": idx, "address": addr, "sats": sats, "script_type": script}
            )
    tx_schema = {
        "txid": pl.String,
        "first_seen_us": pl.Int64,
        "last_seen_us": pl.Int64,
        "n_in": pl.Int32,
        "n_out": pl.Int32,
        "in_sats": pl.Int64,
        "out_sats": pl.Int64,
        "fee_sats": pl.Int64,
        "fee_src": pl.String,
        "is_coinbase": pl.Boolean,
        "n_obs": pl.Int32,
    }
    io_schema = {
        "txid": pl.String,
        "idx": pl.Int32,
        "address": pl.String,
        "sats": pl.Int64,
        "script_type": pl.String,
    }
    con.register("tx_new", pl.DataFrame(tx_rows, schema=tx_schema, orient="row").to_arrow())
    con.execute(
        "INSERT INTO tx (txid, first_seen_us, last_seen_us, n_in, n_out, in_sats, out_sats, fee_sats, fee_src, is_coinbase, n_obs)"
        " SELECT * FROM tx_new"
    )
    con.register("in_new", pl.DataFrame(in_rows, schema=io_schema, orient="row").to_arrow())
    con.execute("INSERT INTO txin (txid, idx, address, sats, script_type) SELECT * FROM in_new")
    con.register("out_new", pl.DataFrame(out_rows, schema=io_schema, orient="row").to_arrow())
    con.execute("INSERT INTO txout SELECT * FROM out_new")
    for name in ("tx_new", "in_new", "out_new"):
        con.unregister(name)
