"""Engine settings: every analysis threshold, with its blueprint default (§17.3). Hashed into each manifest.

Stages read thresholds from here — never from constants in stage code (invariant rule 5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from sutradhar_schemas.canonical import sha256_json


class EngineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int = 2026
    threads: int = Field(default=4, ge=1, le=64)

    # E17 stub (replaced by lead_ranker in P5)
    stub_peel_ratio: float = Field(default=3.0, gt=1)
    peel_min_hops: int = Field(default=3, ge=2)
    peel_max_gap_h: float = Field(
        default=1.0, gt=0, description="Longest pause between hops of one peel chain"
    )
    coinjoin_min_p: float = Field(default=0.5, gt=0, le=1)
    change_merge_min_p: float = Field(default=0.99, gt=0.5, le=1)
    service_min_score: float = Field(
        default=0.6, gt=0, le=1, description="Clusters scoring at least this are treated as services"
    )
    taint_hop_decay: float = Field(
        default=0.97, gt=0, le=1, description="Per-hop multiplier on propagated taint"
    )
    ppr_alpha: float = Field(default=0.85, gt=0.5, lt=1)
    risk_paths_k: int = Field(default=3, ge=1, le=10)
    risk_paths_top: int = Field(default=200, ge=1, le=5000)
    lead_min_p: float = Field(
        default=0.15, gt=0, lt=1, description="Actors scoring below this never become leads"
    )
    lead_limit: int = Field(default=250, ge=10, le=5000, description="Most leads one run publishes")
    family_min_contrib: float = Field(
        default=0.3, gt=0, description="Log-odds an evidence family must add to count"
    )
    recency_halflife_days: float = Field(default=30.0, gt=0)
    cashout_min_taint: float = Field(default=0.03, gt=0, le=1)

    def sha256(self) -> str:
        return sha256_json(self.model_dump(mode="json"))
