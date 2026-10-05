"""Lightweight performance bench: ingest + full pipeline timing on the rich scenario, at increasing sizes.
Usage: uv run python scripts/bench.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_gen.config import PRESETS
from sutradhar_gen.generate import generate


def bench(scenario: str, seed: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        t0 = time.perf_counter()
        summary = generate(PRESETS[scenario], seed, root / "world")
        t_gen = time.perf_counter() - t0
        t0 = time.perf_counter()
        result = ingest([root / "world/data/traffic.csv"], CANONICAL_CSV, root / "ds", "ds_bench")
        t_ingest = time.perf_counter() - t0
        watchlist = root / "world/data/watchlist.csv"
        if watchlist.exists():
            shutil.copy(watchlist, root / "ds/watchlist.csv")
        t0 = time.perf_counter()
        manifest = run_pipeline(root / "ds", root / "run", "run_bench")
        t_run = time.perf_counter() - t0
        return {
            "scenario": scenario,
            "rows": summary["counts"]["observations"],
            "txs": result.capability.txs,
            "generate_s": round(t_gen, 2),
            "ingest_s": round(t_ingest, 2),
            "run_s": round(t_run, 2),
            "stage_ms": {k: v.ms for k, v in manifest.stages.items()},
        }


if __name__ == "__main__":
    results = [bench(s, 1) for s in ("tiny", "demo", "rich")]
    print(json.dumps(results, indent=2))
    for r in results:
        print(
            f"{r['scenario']:6s}: {r['txs']:5d} tx, {r['rows']:6d} obs -> generate {r['generate_s']}s, ingest {r['ingest_s']}s, run {r['run_s']}s"
        )
