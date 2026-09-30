"""P1.8: domain-randomised scenario distributions and the realism report — `sutradhar gen randomize` and
`sutradhar gen validate` (blueprint §5.11-5.12)."""

from __future__ import annotations

from pathlib import Path

from sutradhar_gen.config import PRESETS, ScenarioConfig
from sutradhar_gen.generate import generate
from sutradhar_gen.randomize import randomized_scenarios
from sutradhar_gen.realism import realism_report


def test_randomized_scenarios_are_reproducible_for_the_same_seed_base() -> None:
    a = randomized_scenarios(PRESETS["tiny"], count=5, seed_base=1000)
    b = randomized_scenarios(PRESETS["tiny"], count=5, seed_base=1000)
    assert [seed for seed, _ in a] == [seed for seed, _ in b]
    assert [cfg.model_dump(mode="json") for _, cfg in a] == [cfg.model_dump(mode="json") for _, cfg in b]


def test_randomized_scenarios_actually_vary() -> None:
    variants = randomized_scenarios(PRESETS["rich"], count=8, seed_base=2000)
    user_counts = {cfg.economy.users for _, cfg in variants}
    days = {cfg.time.days for _, cfg in variants}
    assert len(user_counts) > 1
    assert len(days) > 1


def test_randomized_scenario_still_passes_validation() -> None:
    rng_variants = randomized_scenarios(PRESETS["hard"], count=10, seed_base=3000)
    for _, cfg in rng_variants:
        ScenarioConfig.model_validate(cfg.model_dump(mode="json"))  # re-validate: every field stays in bounds


def test_randomized_world_generates_and_stays_deterministic(tmp_path: Path) -> None:
    _, cfg = randomized_scenarios(PRESETS["tiny"], count=1, seed_base=4242)[0]
    s1 = generate(cfg, seed=4242, out=tmp_path / "a")
    s2 = generate(cfg, seed=4242, out=tmp_path / "b")
    assert s1["counts"] == s2["counts"]


def test_realism_report_covers_every_check(tmp_path: Path) -> None:
    cfg = PRESETS["rich"]
    generate(cfg, seed=11, out=tmp_path)
    checks = realism_report(tmp_path, cfg)
    names = {c.name for c in checks}
    assert names == {
        "Inputs/outputs per tx",
        "Address reuse",
        "Script-type mix",
        "Propagation",
        "Degree distribution",
        "CoinJoin share",
        "Label balance",
    }
    # Every check either reports a value or explicitly says why it couldn't (never silently empty).
    assert all(c.value for c in checks)


def test_realism_report_flags_do_not_raise(tmp_path: Path) -> None:
    """Flagged, not fatal (blueprint §5.12): an out-of-band check must never be a crash."""
    cfg = PRESETS["tiny"]
    generate(cfg, seed=1, out=tmp_path)
    checks = realism_report(tmp_path, cfg)
    assert all(c.in_band in (True, False, None) for c in checks)
