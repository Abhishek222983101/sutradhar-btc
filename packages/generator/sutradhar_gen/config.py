"""Scenario configuration. Every knob of the synthetic world lives here, validated, with defaults.

P0.3 uses the core; later phases add sections (benign agents, CoinJoin, typologies, adversary knobs).
A scenario plus a seed fully determines the generated world (byte-identical output).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sutradhar_schemas.enums import ObservationModel, ScriptType

DEFAULT_SCRIPT_MIX: dict[ScriptType, float] = {
    ScriptType.P2WPKH: 0.55,
    ScriptType.P2TR: 0.20,
    ScriptType.P2SH: 0.12,
    ScriptType.P2PKH: 0.10,
    ScriptType.P2WSH: 0.03,
}


class _Cfg(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Range(_Cfg):
    lo: float
    hi: float

    @model_validator(mode="after")
    def _ordered(self) -> Range:
        if self.hi < self.lo:
            raise ValueError("range hi must be >= lo")
        return self


class TimeCfg(_Cfg):
    start: datetime = datetime(2026, 8, 1, tzinfo=UTC)
    days: float = Field(default=3.0, gt=0, le=60)
    warmup_days: float = Field(default=1.0, ge=0, description="Simulated but not exported (funds the world)")
    block_interval_s: float = Field(default=600.0, gt=0)

    @model_validator(mode="after")
    def _warmup_inside(self) -> TimeCfg:
        if self.warmup_days >= self.days:
            raise ValueError("warmup must be shorter than the whole simulation")
        return self


class EconomyCfg(_Cfg):
    users: int = Field(default=100, ge=2)
    exchanges: int = Field(default=1, ge=1)
    user_tx_per_day: float = Field(default=1.0, ge=0)
    user_start_btc: Range = Range(lo=0.02, hi=1.5)
    exchange_start_btc: float = Field(default=400.0, gt=0)
    script_mix: dict[ScriptType, float] = DEFAULT_SCRIPT_MIX
    address_reuse: float = Field(default=0.10, ge=0, le=1)
    feerate_median_sat_vb: float = Field(default=12.0, gt=0)
    feerate_sigma: float = Field(default=0.6, ge=0)
    sweep_every_h: float = Field(default=6.0, gt=0)
    withdrawal_batch_every_h: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def _mix_sums_to_one(self) -> EconomyCfg:
        total = sum(self.script_mix.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"script_mix must sum to 1 (got {total})")
        return self


class RansomwareCfg(_Cfg):
    op_id: str = "ghostline"
    victims: int = Field(default=4, ge=1, le=200)
    ransom_btc: Range = Range(lo=0.2, hi=2.0)
    pay_day: float = Field(default=1.2, ge=0, description="Day (from start) the ransom payments begin")
    consolidate_after_h: float = Field(default=6.0, ge=0)
    peel_hops: int = Field(default=5, ge=1, le=200)
    hop_interval_min: Range = Range(lo=9, hi=15)
    peel_fraction: Range = Range(lo=0.03, hi=0.15)


class CoinJoinCfg(_Cfg):
    """A Whirlpool-style coordinator: each round mixes equal-valued outputs for several participants."""

    op_id: str = "whirlpool"
    rounds: int = Field(default=6, ge=1, le=500)
    participants_min: int = Field(default=5, ge=3, le=60)
    participants_max: int = Field(default=8, ge=3, le=60)
    denomination_btc: float = Field(default=0.05, gt=0)
    first_round_day: float = Field(default=1.2, ge=0)
    interval_h: float = Field(default=10.0, gt=0)


class DarknetCfg(_Cfg):
    """A darknet market: buyers pay escrow addresses, the market consolidates and pays vendors in batches."""

    op_id: str = "bazaar"
    buyers: int = Field(default=10, ge=1, le=500)
    vendors: int = Field(default=3, ge=1, le=50)
    price_btc: Range = Range(lo=0.01, hi=0.06)
    start_day: float = Field(default=1.3, ge=0)
    payout_after_h: float = Field(default=14.0, gt=0)
    cashout_after_h: float = Field(default=3.0, gt=0)


class LookalikeCfg(_Cfg):
    """Legitimate actors whose transaction shapes resemble illicit ones (hard negatives for every detector)."""

    merchants: int = Field(default=0, ge=0, le=50)
    merchant_sales_per_day: float = Field(default=14.0, gt=0)
    merchant_sweep_every_h: float = Field(default=10.0, gt=0)
    payroll_employers: int = Field(default=0, ge=0, le=10)
    payroll_employees: int = Field(default=9, ge=2, le=200)
    payroll_every_h: float = Field(default=20.0, gt=0)
    traders: int = Field(default=0, ge=0, le=50)
    trader_interval_min: Range = Range(lo=45, hi=150)


class OpsCfg(_Cfg):
    ransomware: tuple[RansomwareCfg, ...] = (RansomwareCfg(),)
    coinjoin: tuple[CoinJoinCfg, ...] = ()
    darknet: tuple[DarknetCfg, ...] = ()


class NetworkCfg(_Cfg):
    listeners: int = Field(default=60, ge=10)
    sensors: int = Field(default=5, ge=1)
    outbound: int = Field(default=8, ge=2, le=16)
    sensor_listener_links: int = Field(
        default=20, ge=1, description="Outbound links each sensor makes to listeners"
    )
    client_sensor_prob: float = Field(
        default=0.3, ge=0, le=1, description="Chance a client includes a sensor among its peers"
    )
    inv_mean_outbound_s: float = Field(default=2.0, gt=0)
    inv_mean_inbound_s: float = Field(default=5.0, gt=0)
    latency_median_ms: float = Field(default=60.0, gt=0)
    latency_sigma: float = Field(default=0.5, ge=0)
    ip_space: Literal["testnet", "realistic"] = "testnet"


class ObservationCfg(_Cfg):
    model: ObservationModel = ObservationModel.VANTAGE
    log_first_k: int = Field(
        default=5, ge=1, le=64, description="Each sensor logs the first k announcers per tx"
    )


class ScenarioConfig(_Cfg):
    name: str = Field(default="tiny", pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = ""
    time: TimeCfg = TimeCfg()
    economy: EconomyCfg = EconomyCfg()
    ops: OpsCfg = OpsCfg()
    lookalikes: LookalikeCfg = LookalikeCfg()
    network: NetworkCfg = NetworkCfg()
    observation: ObservationCfg = ObservationCfg()


PRESETS: dict[str, ScenarioConfig] = {
    "rich": ScenarioConfig(
        name="rich",
        description="Ransomware, a CoinJoin coordinator and a darknet market on a busier economy, public-looking IPs.",
        time=TimeCfg(days=5.0, warmup_days=1.0),
        economy=EconomyCfg(users=160, user_tx_per_day=1.2),
        ops=OpsCfg(coinjoin=(CoinJoinCfg(),), darknet=(DarknetCfg(),)),
        lookalikes=LookalikeCfg(merchants=3, payroll_employers=1, traders=3),
        network=NetworkCfg(ip_space="realistic"),
    ),
    "hard": ScenarioConfig(
        name="hard",
        description="Rich, with more look-alike legitimate actors and slower, less regular ransomware laundering.",
        time=TimeCfg(days=5.0, warmup_days=1.0),
        economy=EconomyCfg(users=180, user_tx_per_day=1.2),
        ops=OpsCfg(
            ransomware=(
                RansomwareCfg(hop_interval_min=Range(lo=70, hi=420), peel_fraction=Range(lo=0.02, hi=0.3)),
            ),
            coinjoin=(CoinJoinCfg(),),
            darknet=(DarknetCfg(),),
        ),
        lookalikes=LookalikeCfg(merchants=5, payroll_employers=2, traders=6),
        network=NetworkCfg(ip_space="realistic"),
    ),
    "demo": ScenarioConfig(
        name="demo",
        description="The tiny world with public-looking IPs from an open GeoIP database, for the live demo.",
        network=NetworkCfg(ip_space="realistic"),
    ),
    "tiny": ScenarioConfig(
        name="tiny", description="Seconds to generate: one of everything, for tests and CI."
    ),
}
