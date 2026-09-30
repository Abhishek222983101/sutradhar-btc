"""The lead ranker's inputs and model files. Every feature is computed from observations, ledger and earlier stages
only, never from ground truth (I7). Training lives in `sutradhar_evals`; the engine only loads the result."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODELS_DIR = Path(__file__).parent / "models"

# name -> evidence family used for grouping explanations
FEATURE_FAMILY: dict[str, str] = {
    "log_n_addr": "FLOW",
    "log_tx_sent": "BEHAV",
    "log_tx_recv": "BEHAV",
    "log_counterparties": "FLOW",
    "avg_n_in": "FLOW",
    "avg_n_out": "FLOW",
    "log_sent": "FLOW",
    "log_recv": "FLOW",
    "log_lifetime_h": "BEHAV",
    "consolidation_share": "FLOW",
    "fan_out_share": "FLOW",
    "coinjoin_share": "FLOW",
    "peel_share": "FLOW",
    "peel_len_max": "FLOW",
    "out_service_share": "FLOW",
    "in_service_share": "FLOW",
    "taint_max": "TAINT",
    "taint_in_frac": "TAINT",
    "ppr_log": "TAINT",
    "seed_hops": "TAINT",
    "n_risk_paths": "TAINT",
    "top_ip_share": "NET",
    "n_origin_ips": "NET",
    "mean_origin_p": "NET",
    "unobservable_share": "NET",
    "log_shared_ip_clusters": "NET",
    "country_count": "NET",
    "tx_anom_max": "ANOM",
    "tx_anom_mean": "ANOM",
    "actor_anom": "ANOM",
    "log_fee_rate": "BEHAV",
    "log_gap_h": "BEHAV",
    "night_share": "BEHAV",
    "victim_exposure": "FLOW",
    "service_score": "FLOW",
    "is_cashout": "FLOW",
}
FEATURES: tuple[str, ...] = tuple(FEATURE_FAMILY)
FAMILIES = ("NET", "FLOW", "TAINT", "ANOM", "BEHAV")


@dataclass(frozen=True)
class Calibrator:
    """Isotonic calibration stored as breakpoints; applied with linear interpolation."""

    x: tuple[float, ...]
    y: tuple[float, ...]

    def __call__(self, raw: np.ndarray) -> np.ndarray:
        if not self.x:
            return raw
        return np.interp(raw, self.x, self.y)


@dataclass(frozen=True)
class RankerMeta:
    version: str
    features: tuple[str, ...]
    baseline: dict[str, float]  # "clean actor" values, for counterfactuals
    calibrator: Calibrator
    reference_hist: dict[str, dict[str, list[float]]]  # for drift (PSI)


def load_meta(name: str = "lead_ranker") -> RankerMeta | None:
    path = MODELS_DIR / f"{name}.meta.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    if tuple(d["features"]) != FEATURES:
        raise ValueError("lead_ranker features do not match the engine")
    cal = Calibrator(tuple(d["calibrator"]["x"]), tuple(d["calibrator"]["y"]))
    return RankerMeta(d["version"], FEATURES, d["baseline"], cal, d.get("reference_hist", {}))


def load_booster(name: str = "lead_ranker"):  # type: ignore[no-untyped-def]
    import lightgbm as lgb

    path = MODELS_DIR / f"{name}.txt"
    return lgb.Booster(model_file=str(path)) if path.exists() else None


class Ranker:
    """LightGBM booster + isotonic calibrator. `contributions` are TreeSHAP values in log-odds space."""

    def __init__(self) -> None:
        self.booster = load_booster()
        self.meta = load_meta()
        if self.booster is None or self.meta is None:
            raise FileNotFoundError("lead_ranker model files are missing")
        self.version = self.meta.version

    def raw(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.booster.predict(x, num_threads=1))

    def prob(self, x: np.ndarray) -> np.ndarray:
        return np.clip(self.meta.calibrator(self.raw(x)), 0.0, 1.0)

    def contributions(self, x: np.ndarray) -> np.ndarray:
        """(n, n_features + 1): the last column is the expected value (bias)."""
        return np.asarray(self.booster.predict(x, pred_contrib=True, num_threads=1))


def available() -> bool:
    return (MODELS_DIR / "lead_ranker.txt").exists() and (MODELS_DIR / "lead_ranker.meta.json").exists()


def model_versions() -> dict[str, str]:
    """Versions of every trained model file that ships with the engine (recorded in each run manifest)."""
    versions: dict[str, str] = {}
    for name, filename in (
        ("origin", "origin_lr.json"),
        ("change", "change_lr.json"),
        ("lead_ranker", "lead_ranker.meta.json"),
    ):
        path = MODELS_DIR / filename
        if path.exists():
            versions[name] = json.loads(path.read_text(encoding="utf-8")).get("version", "unknown")
    return versions
