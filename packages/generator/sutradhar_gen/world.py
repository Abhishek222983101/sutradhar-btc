"""The simulated world: a deterministic event clock driving agents over a UTXO ledger.

Randomness comes from named streams spawned from one SeedSequence, so adding a new stream never shifts
the numbers another component draws — scenarios stay reproducible as the generator grows.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from sutradhar_gen.config import Range, ScenarioConfig
from sutradhar_gen.economy import Ledger, Wallet
from sutradhar_schemas.enums import ScriptType
from sutradhar_schemas.units import SATS_PER_BTC, utc_micros

US_PER_S = 1_000_000
US_PER_H = 3_600 * US_PER_S
US_PER_DAY = 24 * US_PER_H

STREAMS = (
    "ledger",
    "agents",
    "ops",
    "fees",
    "network",
    "propagation",
    "observation",
    "export",
    "coinjoin",
    "darknet",
    "lookalike",
)


@dataclass(slots=True)
class Agent:
    agent_id: str
    kind: str  # user | exchange | ransomware | relay | sensor
    illicit: bool = False
    op_id: str | None = None
    wallet_ids: list[str] = field(default_factory=list)
    node_id: int | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


class World:
    def __init__(self, cfg: ScenarioConfig, seed: int) -> None:
        self.cfg = cfg
        self.seed = seed
        children = np.random.SeedSequence(seed).spawn(len(STREAMS))
        self.rng: dict[str, np.random.Generator] = {
            name: np.random.default_rng(child) for name, child in zip(STREAMS, children, strict=True)
        }
        self.ledger = Ledger(self.rng["ledger"])
        self.agents: dict[str, Agent] = {}
        self.t0 = utc_micros(cfg.time.start)
        self.t_export = self.t0 + int(cfg.time.warmup_days * US_PER_DAY)
        self.t_end = self.t0 + int(cfg.time.days * US_PER_DAY)
        self._events: list[tuple[int, int, Callable[..., None], tuple[Any, ...]]] = []
        self._seq = 0
        self.now = self.t0

    # -- scheduling ---------------------------------------------------------------------------------
    def schedule(self, t_us: int, fn: Callable[..., None], *args: Any) -> None:
        if t_us < self.t_end:
            heapq.heappush(self._events, (t_us, self._seq, fn, args))
            self._seq += 1

    def run(self) -> None:
        while self._events:
            t_us, _, fn, args = heapq.heappop(self._events)
            self.now = t_us
            fn(*args)

    # -- helpers ------------------------------------------------------------------------------------
    def add_agent(self, agent: Agent) -> Agent:
        if agent.agent_id in self.agents:
            raise ValueError(f"duplicate agent {agent.agent_id}")
        self.agents[agent.agent_id] = agent
        return agent

    def new_wallet(
        self, agent: Agent, suffix: str, script: ScriptType | None = None, reuse: float | None = None
    ) -> Wallet:
        script = script or self.pick_script(self.rng["agents"])
        wallet = Wallet(
            wallet_id=f"{agent.agent_id}/{suffix}",
            agent_id=agent.agent_id,
            script=script,
            reuse_prob=self.cfg.economy.address_reuse if reuse is None else reuse,
            change_last=bool(self.rng["agents"].random() < 0.5),
        )
        self.ledger.add_wallet(wallet)
        agent.wallet_ids.append(wallet.wallet_id)
        return wallet

    def pick_script(self, rng: np.random.Generator) -> ScriptType:
        mix = self.cfg.economy.script_mix
        scripts = sorted(mix, key=str)
        probs = np.array([mix[s] for s in scripts], dtype=float)
        return scripts[int(rng.choice(len(scripts), p=probs / probs.sum()))]

    def feerate(self, t_us: int) -> float:
        """sat/vB: log-normal around the median with a gentle daily congestion cycle."""
        econ = self.cfg.economy
        day_phase = ((t_us - self.t0) % US_PER_DAY) / US_PER_DAY
        cycle = 1.0 + 0.35 * math.sin(2 * math.pi * (day_phase - 0.25))
        draw = float(self.rng["fees"].lognormal(math.log(econ.feerate_median_sat_vb), econ.feerate_sigma))
        return max(1.0, round(draw * cycle, 2))

    @staticmethod
    def draw_range(rng: np.random.Generator, rng_range: Range, *, log: bool = False) -> float:
        if rng_range.hi == rng_range.lo:
            return rng_range.lo
        if log and rng_range.lo > 0:
            return float(math.exp(rng.uniform(math.log(rng_range.lo), math.log(rng_range.hi))))
        return float(rng.uniform(rng_range.lo, rng_range.hi))

    @staticmethod
    def btc(value: float) -> int:
        """BTC float drawn by the simulator → satoshis (rounded to whole satoshis)."""
        return round(value * SATS_PER_BTC)
