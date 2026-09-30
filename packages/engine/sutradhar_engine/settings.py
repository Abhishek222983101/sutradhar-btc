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
    coinjoin_min_p: float = Field(default=0.5, gt=0, le=1)

    def sha256(self) -> str:
        return sha256_json(self.model_dump(mode="json"))
