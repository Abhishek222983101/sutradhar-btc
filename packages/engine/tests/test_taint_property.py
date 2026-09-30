"""Property tests for haircut taint on random transaction graphs (Hypothesis)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from sutradhar_engine.stages.e13_taint import propagate

ADDR = [f"a{i:02d}" for i in range(14)]


@st.composite
def dag(draw):  # type: ignore[no-untyped-def]
    """Transactions in time order; every input is an address that has appeared before (or is a fresh source)."""
    n = draw(st.integers(1, 25))
    seen: list[str] = [ADDR[0]]
    txs = []
    for i in range(n):
        k_in = draw(st.integers(1, min(3, len(seen))))
        ins = draw(st.lists(st.sampled_from(seen), min_size=k_in, max_size=k_in, unique=True))
        sats_in = [draw(st.integers(1_000, 5_000_000)) for _ in ins]
        n_out = draw(st.integers(1, 3))
        outs_addr = draw(st.lists(st.sampled_from(ADDR), min_size=n_out, max_size=n_out, unique=True))
        remaining = sum(sats_in)
        outs = []
        for j, a in enumerate(outs_addr):
            part = remaining if j == n_out - 1 else draw(st.integers(1, max(1, remaining - (n_out - j - 1))))
            outs.append((a, part))
            remaining -= part
        seen += [a for a, _ in outs if a not in seen]
        txs.append((f"t{i}", ins, sats_in, outs))
    return txs


seeds_st = st.dictionaries(
    st.sampled_from(ADDR), st.tuples(st.floats(0.1, 1.0), st.just("test")), min_size=1, max_size=3
)
services_st = st.sets(st.sampled_from(ADDR), max_size=3)


@settings(max_examples=150, deadline=None)
@given(txs=dag(), seeds=seeds_st, services=services_st)
def test_taint_is_a_bounded_fraction_and_seeds_never_lose_it(txs, seeds, services) -> None:  # type: ignore[no-untyped-def]
    taint, hops, _ = propagate(txs, seeds, services, 0.97)
    assert all(0.0 <= t <= 1.0 for t in taint.values())
    for address, (confidence, _) in seeds.items():
        assert taint[address] >= confidence
        assert hops[address] == 0


def _replay(txs, seeds, services):  # type: ignore[no-untyped-def]
    """Yield (tx, taint before it, taint after it), replaying the graph one transaction at a time."""
    before, _, _ = propagate([], seeds, services, 0.97)
    for i, tx in enumerate(txs):
        after, _, _ = propagate(txs[: i + 1], seeds, services, 0.97)
        yield tx, before, after
        before = after


@settings(max_examples=100, deadline=None)
@given(txs=dag(), seeds=seeds_st, services=services_st)
def test_taint_conserves_value(txs, seeds, services) -> None:  # type: ignore[no-untyped-def]
    """No transaction creates tainted value: whatever fraction its outputs gain, times the transaction's size,
    never exceeds the tainted value its (non-service) inputs carried."""
    for (_txid, ins, sats, outs), before, after in _replay(txs, seeds, services):
        carried = sum(before.get(a, 0.0) * s for a, s in zip(ins, sats, strict=True) if a not in services)
        for address, _ in outs:
            if after.get(address, 0.0) > before.get(address, 0.0):
                assert after[address] * sum(sats) <= carried + 1e-6


@settings(max_examples=100, deadline=None)
@given(txs=dag(), seeds=seeds_st, services=services_st)
def test_taint_stops_at_services(txs, seeds, services) -> None:  # type: ignore[no-untyped-def]
    """A transaction that spends only service addresses passes nothing on."""
    for (_txid, ins, _sats, outs), before, after in _replay(txs, seeds, services):
        if all(a in services for a in ins):
            assert all(after.get(a, 0.0) == before.get(a, 0.0) for a, _ in outs)


def test_taint_decays_with_each_hop() -> None:
    chain = [(f"t{i}", [f"x{i}"], [1000], [(f"x{i + 1}", 1000)]) for i in range(5)]
    taint, hops, _ = propagate(chain, {"x0": (1.0, "t")}, set(), 0.9)
    values = [taint[f"x{i}"] for i in range(6)]
    assert values == sorted(values, reverse=True) and hops["x5"] == 5
    assert values[1] == 0.9 and values[5] < values[1]  # every hop multiplies by the decay


def test_service_is_a_dead_end() -> None:
    chain = [("t0", ["s"], [1000], [("svc", 1000)]), ("t1", ["svc"], [1000], [("after", 1000)])]
    taint, _, stopped = propagate(chain, {"s": (1.0, "t")}, {"svc"}, 1.0)
    assert taint["svc"] > 0 and "after" not in taint and stopped == 1
