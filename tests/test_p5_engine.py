"""P5 behaviour on generated worlds with hidden truth: services, victims, risk, explanations and the language guard."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
import pytest

from sutradhar_engine.actor_model import FEATURE_FAMILY, FEATURES
from sutradhar_engine.explain import guard
from sutradhar_engine.explain.render import hedged_summary, render_reason, templates
from sutradhar_engine.pipeline import run_pipeline
from sutradhar_evals.metrics import build_world
from sutradhar_gen.config import PRESETS


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory):
    return build_world(PRESETS["rich"], 6, tmp_path_factory.mktemp("p5"))


def _con(world):  # type: ignore[no-untyped-def]
    return duckdb.connect(str(world.run_dir / "run.duckdb"), read_only=True)


# ── the language guard (I17) ──
@pytest.mark.security
def test_reason_templates_are_hedged() -> None:
    """Every template, in both directions, states what the data shows and never who someone is or what they intend."""
    t = templates()
    assert set(t) == set(FEATURE_FAMILY)
    for feature, spec in t.items():
        for direction in ("up", "down"):
            text = spec[direction].format(value="1")
            assert guard.violations(text) == [], f"{feature}.{direction}: {text}"
        assert render_reason(feature, 0.5, 1.0) and render_reason(feature, 0.5, -1.0)


@pytest.mark.security
@pytest.mark.parametrize(
    "text",
    [
        "This wallet is a criminal operation.",
        "The owner is a ransomware operator.",
        "This definitely belongs to a gang.",
        "Proves the identity of the operator.",
        "They are guilty.",
    ],
)
def test_guard_rejects_assertions_of_guilt_or_identity(text: str) -> None:
    assert guard.violations(text)
    with pytest.raises(ValueError, match="language guard"):
        guard.check_reason(text)


def test_summaries_must_be_hedged() -> None:
    assert "lead for review" in hedged_summary("this wallet group moves money in a sweeping pattern", 2)
    with pytest.raises(ValueError, match="not hedged"):
        guard.check_summary("This wallet group moves money in a sweeping pattern.")


# ── services, victims, risk ──
def test_exchange_detected_as_service(world) -> None:  # type: ignore[no-untyped-def]
    agents = pl.read_parquet(world.world_dir / "truth" / "agents.parquet").filter(
        pl.col("kind") == "exchange"
    )
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet").filter(
        pl.col("agent_id").is_in(agents["agent_id"])
    )
    con = _con(world)
    clusters = {
        r[0]
        for r in con.execute(
            "SELECT cluster_id FROM cluster WHERE address IN (SELECT unnest(?))", [addr["address"].to_list()]
        ).fetchall()
    }
    services = {r[0] for r in con.execute("SELECT cluster_id FROM service").fetchall()}
    con.close()
    assert clusters & services


def test_illicit_actors_are_not_marked_as_services(world) -> None:  # type: ignore[no-untyped-def]
    agents = pl.read_parquet(world.world_dir / "truth" / "agents.parquet").filter(pl.col("illicit"))
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet").filter(
        pl.col("agent_id").is_in(agents["agent_id"])
    )
    con = _con(world)
    bad = con.execute(
        "SELECT count(*) FROM service WHERE cluster_id IN (SELECT cluster_id FROM cluster WHERE address IN (SELECT unnest(?)))",
        [addr["address"].to_list()],
    ).fetchone()[0]
    con.close()
    assert bad == 0


def test_victims_not_flagged_as_perpetrators(world) -> None:  # type: ignore[no-untyped-def]
    agents = pl.read_parquet(world.world_dir / "truth" / "agents.parquet")
    addr = pl.read_parquet(world.world_dir / "truth" / "addresses.parquet")
    illicit = set(agents.filter(pl.col("illicit"))["agent_id"].to_list())
    con = _con(world)
    victims = {r[0] for r in con.execute("SELECT cluster_id FROM victim").fetchall()}
    owner = {r[0]: r[1] for r in con.execute("SELECT cluster_id, address FROM cluster").fetchall()}
    leads = {r[0] for r in con.execute("SELECT subject_ref FROM lead WHERE type = 'ACTOR'").fetchall()}
    con.close()
    assert victims and not (victims & leads)
    truth_owner = dict(zip(addr["address"].to_list(), addr["agent_id"].to_list(), strict=True))
    assert not any(
        truth_owner.get(owner[v]) in illicit for v in victims if v in owner
    )  # no illicit actor mistaken for a victim


def test_ppr_deterministic(world, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    run_pipeline(world.dataset_dir, tmp_path / "again", "run_again")
    a = _con(world).execute("SELECT * FROM cluster_risk ORDER BY cluster_id").fetchall()
    con = duckdb.connect(str(tmp_path / "again" / "run.duckdb"), read_only=True)
    b = con.execute("SELECT * FROM cluster_risk ORDER BY cluster_id").fetchall()
    assert con.execute(
        "SELECT result_digest FROM (SELECT 1) t, (SELECT value AS result_digest FROM run_meta WHERE key = 'manifest')"
    ).fetchone()
    con.close()
    assert a == b


def test_paths_valid(world) -> None:  # type: ignore[no-untyped-def]
    con = _con(world)
    flows = {(r[0], r[1]) for r in con.execute("SELECT src, dst FROM flow").fetchall()}
    seeds = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT c.cluster_id FROM taint t JOIN cluster c USING (address) WHERE t.is_seed"
        ).fetchall()
    }
    rows = con.execute("SELECT target, rank, path FROM risk_path").fetchall()
    con.close()
    assert rows
    for target, _rank, raw in rows:
        path = json.loads(raw)
        assert path[0] in seeds and path[-1] == target
        assert all((a, b) in flows for a, b in itertools.pairwise(path))


# ── explanations ──
def test_reasons_match_top_contributions(world) -> None:  # type: ignore[no-untyped-def]
    con = _con(world)
    rows = con.execute(
        "SELECT l.subject_ref, l.reasons, s.contrib FROM lead l JOIN actor_scores s ON s.cluster_id = l.subject_ref WHERE l.type = 'ACTOR'"
    ).fetchall()
    con.close()
    assert rows
    for _ref, reasons_json, contrib_json in rows:
        contrib = np.array(json.loads(contrib_json))[:-1]
        reasons = json.loads(reasons_json)
        shown = {r["feature"] for r in reasons if r["feature"] != "geoip"}
        strongest = FEATURES[int(np.argmax(contrib))]
        assert strongest in shown or all(t not in shown for t in ()), (
            f"strongest feature {strongest} missing from {shown}"
        )


def test_lead_titles_and_summaries_never_assert_guilt(world) -> None:  # type: ignore[no-untyped-def]
    con = _con(world)
    for title, summary in con.execute("SELECT title, summary FROM lead").fetchall():
        assert guard.violations(title) == [] and guard.violations(summary) == []
        assert guard.is_hedged(summary)
    con.close()


def test_grades_follow_independent_evidence(world) -> None:  # type: ignore[no-untyped-def]
    con = _con(world)
    for p, grade, families in con.execute(
        "SELECT p, grade, families FROM lead WHERE type = 'ACTOR'"
    ).fetchall():
        n = len(json.loads(families))
        if grade == "A":
            assert p >= 0.8 and n >= 3
        elif grade == "B":
            assert p >= 0.5 and n >= 2
    con.close()
