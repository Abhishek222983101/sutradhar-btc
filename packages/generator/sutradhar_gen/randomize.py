"""Domain randomisation (P1.8, blueprint §5.11): every trained-on world should sample its parameters from
ranges, not reuse the hero/demo defaults verbatim, so models learn invariances rather than one fixed
configuration. Scoped to the knobs this generator actually exposes (economy, network, lookalikes, time) —
the blueprint's full range (NAT sharing, Tor/VPN, per-typology adversary knobs) needs simulation machinery
this generator doesn't have yet; randomising the knobs that exist is still a real, checkable improvement over
"every training world is `rich` or `hard`, verbatim."
"""

from __future__ import annotations

import numpy as np

from sutradhar_gen.config import ScenarioConfig
from sutradhar_schemas.enums import ScriptType

COIN_SELECTIONS = ("largest_first", "fifo", "random")


def _dirichlet_script_mix(
    base: dict[ScriptType, float], rng: np.random.Generator, concentration: float
) -> dict[ScriptType, float]:
    """A random script mix that stays *centred on* `base`: higher `concentration` means less drift."""
    types = sorted(base, key=str)
    alpha = np.array([max(base[t], 1e-3) * concentration for t in types])
    draw = rng.dirichlet(alpha)
    return dict(zip(types, (float(x) for x in draw), strict=True))


def domain_randomize(base: ScenarioConfig, rng: np.random.Generator) -> ScenarioConfig:
    """One randomised variant of `base`. Deterministic for a given `rng` state, so a `--seed-base` plus an
    index gives byte-identical worlds across runs, same as every other part of the generator."""
    econ = base.economy
    net = base.network
    lk = base.lookalikes
    time_ = base.time

    days = float(rng.uniform(1.5, 7.0))
    warmup = min(time_.warmup_days, days * 0.3)

    users = int(np.clip(econ.users * rng.uniform(0.3, 3.0), 20, 500))
    outbound = int(np.clip(net.outbound + rng.integers(-2, 3), 2, 16))
    sensors = int(np.clip(net.sensors + rng.integers(-2, 6), 3, 20))

    return base.model_copy(
        update={
            "time": time_.model_copy(update={"days": days, "warmup_days": warmup}),
            "economy": econ.model_copy(
                update={
                    "users": users,
                    "script_mix": _dirichlet_script_mix(econ.script_mix, rng, concentration=40.0),
                    "address_reuse": float(rng.uniform(0.0, 0.30)),
                    "coin_selection": COIN_SELECTIONS[int(rng.integers(len(COIN_SELECTIONS)))],
                    "feerate_median_sat_vb": float(rng.uniform(3.0, 60.0)),  # calm vs. congested regime
                }
            ),
            "network": net.model_copy(
                update={
                    "sensors": sensors,
                    "outbound": outbound,
                    "inv_mean_outbound_s": float(rng.uniform(1.0, 6.0)),
                    "inv_mean_inbound_s": float(rng.uniform(2.0, 10.0)),
                    "latency_median_ms": float(net.latency_median_ms * rng.uniform(0.5, 2.0)),
                }
            ),
            "lookalikes": lk.model_copy(
                update={
                    "merchants": int(rng.integers(0, max(1, econ.users // 20))),
                    "payroll_employers": int(rng.integers(0, 3)),
                    "traders": int(rng.integers(0, max(1, econ.users // 25))),
                }
            ),
        }
    )


def randomized_scenarios(
    base: ScenarioConfig, count: int, seed_base: int
) -> list[tuple[int, ScenarioConfig]]:
    """`count` randomised variants of `base`, each with its own seed — `(seed, config)` pairs, ready for
    `generate()`. Every variant is fully determined by `seed_base`: rerunning with the same base and
    `seed_base` reproduces the exact same list, config-for-config."""
    out = []
    for i in range(count):
        seed = seed_base + i
        rng = np.random.default_rng(np.random.SeedSequence([seed_base, i]))
        out.append((seed, domain_randomize(base, rng)))
    return out
