"""Small JSON-weight logistic models shared by engine stages. Training happens in `sutradhar_evals` (needs truth);
the engine only reads weights, so it can never see ground truth (I7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"


@dataclass(frozen=True)
class LinearModel:
    features: tuple[str, ...]
    weights: tuple[float, ...]
    bias: float
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    version: str

    def logit_sql(self) -> str:
        terms = [
            f"({w!r} * (({name} - {m!r}) / {s!r}))"
            for name, w, m, s in zip(self.features, self.weights, self.mean, self.scale, strict=True)
        ]
        return f"({self.bias!r} + " + " + ".join(terms) + ")"


def load(name: str, features: tuple[str, ...]) -> LinearModel | None:
    path = MODELS_DIR / f"{name}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if tuple(data["features"]) != features:
        raise ValueError(f"model {name}: feature list does not match the engine")
    return LinearModel(
        features,
        tuple(data["weights"]),
        float(data["bias"]),
        tuple(data["mean"]),
        tuple(data["scale"]),
        data["version"],
    )
