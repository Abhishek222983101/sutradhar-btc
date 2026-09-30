"""Build the demo "hero" world: generate, ingest, analyse, and pack it as apps/api/sutradhar_api/demo/hero.tar.gz.

The demo server unpacks this archive at boot instead of re-running the analysis, so the first request is instant and
the demo needs no compute. Re-run after any change to the engine or models (a test checks the archive still matches):
    uv run python scripts/build_hero.py
"""

from __future__ import annotations

import shutil
import tarfile
import tempfile
from pathlib import Path

from sutradhar_engine.ingest.builtin_profiles import CANONICAL_CSV
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_engine.settings import EngineSettings
from sutradhar_gen.config import PRESETS
from sutradhar_gen.generate import generate

OUT = Path(__file__).resolve().parents[1] / "apps/api/sutradhar_api/demo/hero.tar.gz"
SCENARIO, SEED = "rich", 2


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        generate(PRESETS[SCENARIO], SEED, root / "world")
        ds = root / "datasets" / "ds_hero"
        ingest([root / "world/data/traffic.csv"], CANONICAL_CSV, ds, "ds_hero")
        shutil.copy(root / "world/data/watchlist.csv", ds / "watchlist.csv")
        run_pipeline(ds, root / "runs" / "run_hero", "run_hero", settings=EngineSettings(threads=2))
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(OUT, "w:gz", compresslevel=9) as tar:
            for path in sorted((root / "datasets").rglob("*")) + sorted((root / "runs").rglob("*")):
                if path.is_file():
                    tar.add(path, arcname=str(path.relative_to(root)))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
