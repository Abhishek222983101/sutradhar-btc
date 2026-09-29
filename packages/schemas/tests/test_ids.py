"""Identifiers: minted ULID ids and the guard for ids that become directory names."""

from __future__ import annotations

import pytest


@pytest.mark.security
@pytest.mark.parametrize("bad", ["../x", "ds_/x", "ds_.", "ds_a b", "DS_a", "ds_a\n", "run_a", "ds_-a", ""])
def test_check_id_refuses_unsafe_ids(bad: str) -> None:
    from sutradhar_schemas.ids import check_id

    with pytest.raises(ValueError, match="invalid ds id"):
        check_id(bad, "ds")


def test_check_id_accepts_minted_and_readable_ids() -> None:
    from sutradhar_schemas.ids import check_id, new_id

    minted = new_id("ds")
    assert check_id(minted, "ds") == minted
    assert check_id("ds_demo-2026_a", "ds") == "ds_demo-2026_a"
