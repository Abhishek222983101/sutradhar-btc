from __future__ import annotations

from pathlib import Path

from sutradhar_schemas.docs import render_contract_markdown

ROOT = Path(__file__).resolve().parents[3]


def test_data_contract_doc_up_to_date() -> None:
    """docs/data-contract.md is generated; regenerate with `uv run sutradhar schemas export`."""
    committed = (ROOT / "docs" / "data-contract.md").read_text(encoding="utf-8")
    assert committed == render_contract_markdown()
