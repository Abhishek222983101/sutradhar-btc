"""P1.7: `gen run` can now write JSON/NDJSON/XML directly, not just CSV — closing the gap where the engine's
readers already accepted all four (packages/engine/tests/test_formats.py) but the generator only ever produced
CSV. All four formats must ingest to byte-identical normalised content."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from sutradhar_engine.digest import table_digest
from sutradhar_engine.ingest.builtin_profiles import BUILTIN_PROFILES
from sutradhar_engine.ingest.pipeline import ingest
from sutradhar_gen.config import PRESETS
from sutradhar_gen.generate import generate

FORMATS = {
    "csv": ("traffic.csv", "canonical-v1"),
    "json": ("traffic.json", "canonical-json-v1"),
    "ndjson": ("traffic.ndjson", "canonical-ndjson-v1"),
    "xml": ("traffic.xml", "canonical-xml-v1"),
}


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_generate_writes_the_requested_format(tmp_path: Path, fmt: str) -> None:
    filename, _ = FORMATS[fmt]
    summary = generate(PRESETS["tiny"], seed=5, out=tmp_path, fmt=fmt)
    assert (tmp_path / "data" / filename).exists()
    assert summary["counts"]["observations"] > 0


def test_all_four_formats_ingest_to_identical_content(tmp_path: Path) -> None:
    digests = set()
    for fmt, (filename, profile) in FORMATS.items():
        world_dir = tmp_path / fmt
        generate(PRESETS["tiny"], seed=9, out=world_dir, fmt=fmt)
        result = ingest(
            [world_dir / "data" / filename], BUILTIN_PROFILES[profile], tmp_path / f"ds_{fmt}", f"ds_{fmt}"
        )
        assert result.capability.quality["rejects"] == 0, fmt
        con = duckdb.connect(str(result.path / "dataset.duckdb"), read_only=True)
        digests.add(
            (
                table_digest(con, "tx", ["txid"]),
                table_digest(con, "txout", ["txid", "idx"]),
                table_digest(con, "obs", ["obs_i"], exclude=("file_id", "row_no")),
            )
        )
        con.close()
    assert len(digests) == 1, "every format must normalise to the same content"


def test_unknown_format_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown format"):
        generate(PRESETS["tiny"], seed=1, out=tmp_path, fmt="yaml")
