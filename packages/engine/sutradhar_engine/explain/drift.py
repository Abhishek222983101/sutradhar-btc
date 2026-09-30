"""Drift: how different is this run's actor population from the one the ranker was trained on? (PSI per feature.)"""

from __future__ import annotations

import numpy as np

from sutradhar_engine.actor_model import FEATURES, RankerMeta

EPS = 1e-4


def psi(reference_edges: list[float], reference_frac: list[float], values: np.ndarray) -> float:
    counts, _ = np.histogram(np.clip(values, reference_edges[0], reference_edges[-1]), bins=reference_edges)
    actual = counts / max(1, len(values))
    expected = np.array(reference_frac)
    a, e = np.maximum(actual, EPS), np.maximum(expected, EPS)
    return float(np.sum((a - e) * np.log(a / e)))


def drift_report(meta: RankerMeta, x: np.ndarray) -> dict[str, object]:
    """PSI below 0.1 is stable, 0.1 to 0.25 moderate, above 0.25 a real shift (the usual convention)."""
    per: dict[str, float] = {}
    for j, name in enumerate(FEATURES):
        ref = meta.reference_hist.get(name)
        if ref and len(x) >= 20:
            per[name] = round(psi(ref["edges"], ref["frac"], x[:, j]), 4)
    worst = max(per.values(), default=0.0)
    level = "high" if worst > 0.25 else "moderate" if worst > 0.1 else "none"
    return {
        "level": level,
        "max_psi": round(worst, 4),
        "shifted": sorted([n for n, v in per.items() if v > 0.25])[:8],
    }
