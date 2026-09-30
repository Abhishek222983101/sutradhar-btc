"""`sutradhar selftest`: prove the installed system works with no network (I1, I3, I4, I5)."""

from __future__ import annotations

import socket
import tempfile
from collections.abc import Callable
from pathlib import Path


def _checks(tmp: Path) -> list[tuple[str, Callable[[], str]]]:
    state: dict[str, object] = {}

    def generate() -> str:
        from sutradhar_gen.config import PRESETS
        from sutradhar_gen.generate import generate as gen

        summary = gen(PRESETS["demo"], 7, tmp / "world")
        state["csv"] = tmp / "world" / "data" / "traffic.csv"
        return f"{summary['counts']['txs_exported']} transactions, {summary['counts']['observations']} observations"

    def ingest() -> str:
        from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
        from sutradhar_engine.ingest.pipeline import ingest as run_ingest

        result = run_ingest([state["csv"]], CANONICAL_CSV, tmp / "ds", "ds_selftest")  # type: ignore[list-item]
        if result.capability.quality["rejects"]:
            raise AssertionError("unexpected rejects")
        return f"{result.capability.rows} rows, model {result.capability.network.observation_model}"

    def run_twice() -> str:
        from sutradhar_engine.pipeline import run_pipeline

        a = run_pipeline(tmp / "ds", tmp / "run_a", "run_a")
        b = run_pipeline(tmp / "ds", tmp / "run_b", "run_b")
        if a.result_digest != b.result_digest:
            raise AssertionError("same input gave different result digests (I4)")
        state["run"] = tmp / "run_a" / "run.duckdb"
        return f"identical result digest {a.result_digest[:12]}"

    def leads() -> str:
        import duckdb

        con = duckdb.connect(str(state["run"]), read_only=True)  # type: ignore[arg-type]
        n = con.execute("SELECT count(*) FROM lead").fetchone()[0]
        origin = con.execute("SELECT count(*) FROM origin").fetchone()[0]
        con.close()
        if not n or not origin:
            raise AssertionError("no leads or origin candidates produced")
        return f"{n} leads, {origin} origin candidates"

    def immutable() -> str:
        import os

        path = Path(state["run"])  # type: ignore[arg-type]
        if os.access(path, os.W_OK):
            raise AssertionError("a finished run is writable (I3)")
        return "finished runs are read-only"

    def geoip() -> str:
        from sutradhar_engine.geoip import lookup

        r = lookup("8.8.8.8")
        if r.country != "US":
            raise AssertionError(f"GeoIP returned {r.country}")
        return f"8.8.8.8 -> {r.country}, AS{r.asn}"

    def audit_chain() -> str:
        from sutradhar_api import audit, migrate
        from sutradhar_api.db import Database

        url = f"sqlite:///{tmp}/app.sqlite"
        migrate.upgrade(url)
        db = Database(url)
        with db.write() as s:
            for i in range(5):
                audit.append(
                    s,
                    actor_id=None,
                    actor_role="system",
                    action="selftest",
                    target_kind="x",
                    target_ref=str(i),
                )
            s.commit()
        with db.read() as s:
            result = audit.verify(s)
        db.dispose()
        if not result.ok:
            raise AssertionError(f"audit chain broken: {result.reason}")
        return f"{result.entries} entries verified"

    def offline() -> str:
        from sutradhar_api import offline_guard

        offline_guard.install("on")
        try:
            with socket.socket() as sock:
                sock.settimeout(1)
                try:
                    sock.connect(("1.1.1.1", 443))
                except offline_guard.OfflineGuardError:
                    return "outbound connection to a public address was refused"
                raise AssertionError("the offline guard let a public connection through (I1)")
        finally:
            offline_guard.uninstall()

    return [
        ("generate a synthetic world", generate),
        ("ingest it", ingest),
        ("run the engine twice (deterministic)", run_twice),
        ("leads and origin candidates exist", leads),
        ("finished run is read-only", immutable),
        ("offline GeoIP", geoip),
        ("audit chain verifies", audit_chain),
        ("offline guard blocks outbound traffic", offline),
    ]


def run() -> bool:
    ok = True
    with tempfile.TemporaryDirectory(prefix="sutradhar-selftest-") as tmp:
        for name, check in _checks(Path(tmp)):
            try:
                detail = check()
                print(f"PASS  {name}: {detail}")
            except Exception as exc:
                ok = False
                print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
                break
    print("selftest passed" if ok else "selftest FAILED")
    return ok
