"""The origin model: a logistic regression over per-candidate timing features, applied per transaction.

Training lives in `sutradhar_evals` (it needs ground truth). The engine only reads the resulting JSON weights,
so nothing here can see truth (I7). If no weights are present the engine falls back to a transparent formula.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MODEL_PATH = Path(__file__).parent / "models" / "origin_lr.json"
FEATURES = ("dt_s", "decay", "rank", "is_first", "sensors_heard", "n_cand", "ip_first_rate", "log_ip_obs")

# One row per (transaction, announcing IP); every feature is computed from observations only.
FEATURE_SQL = """
CREATE OR REPLACE TEMP TABLE origin_feat AS
WITH heard AS (
  SELECT txid, src_ip AS ip, min(ts_us) AS t, count(DISTINCT dst_ip) AS sensors_heard, count(*) AS n_obs
  FROM ds.obs WHERE src_ip IS NOT NULL GROUP BY 1, 2
), base AS (
  SELECT *, (t - min(t) OVER (PARTITION BY txid)) / 1e6 AS dt_s,
         row_number() OVER (PARTITION BY txid ORDER BY t, ip) AS rank,
         count(*) OVER (PARTITION BY txid) AS n_cand FROM heard
), prior AS (
  SELECT ip, avg(CASE WHEN rank = 1 THEN 1.0 ELSE 0.0 END) AS ip_first_rate, count(*) AS ip_obs FROM base GROUP BY ip
)
SELECT b.txid, b.ip, b.t, b.dt_s, exp(-b.dt_s / 0.25) AS decay, b.rank::DOUBLE AS rank,
       (b.rank = 1)::DOUBLE AS is_first, b.sensors_heard::DOUBLE AS sensors_heard, b.n_cand::DOUBLE AS n_cand,
       p.ip_first_rate, ln(1 + p.ip_obs) AS log_ip_obs
FROM base b JOIN prior p USING (ip)
"""


@dataclass(frozen=True)
class OriginModel:
    weights: tuple[float, ...]
    bias: float
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    version: str

    def logit_sql(self) -> str:
        terms = [
            f"({w!r} * (({name} - {m!r}) / {s!r}))"
            for name, w, m, s in zip(FEATURES, self.weights, self.mean, self.scale, strict=True)
        ]
        return f"({self.bias!r} + " + " + ".join(terms) + ")"


def load_model(path: Path = MODEL_PATH) -> OriginModel | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if tuple(data["features"]) != FEATURES:
        raise ValueError("origin model feature list does not match the engine")
    return OriginModel(
        tuple(data["weights"]),
        float(data["bias"]),
        tuple(data["mean"]),
        tuple(data["scale"]),
        data["version"],
    )
