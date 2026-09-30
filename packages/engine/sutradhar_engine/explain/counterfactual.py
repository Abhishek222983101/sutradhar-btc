"""Counterfactuals: "what would clear this?" Set the strongest evidence back to a typical clean value and re-score."""

from __future__ import annotations

from typing import Any

import numpy as np

from sutradhar_engine.actor_model import FEATURES, Ranker

# Features an analyst could meaningfully "remove"; structural ones (size, age) are not counterfactual levers.
LEVERS = (
    "taint_max",
    "taint_in_frac",
    "ppr_log",
    "seed_hops",
    "n_risk_paths",
    "top_ip_share",
    "peel_share",
    "peel_len_max",
    "out_service_share",
    "is_cashout",
    "tx_anom_max",
    "actor_anom",
    "coinjoin_share",
    "consolidation_share",
)


def counterfactuals(ranker: Ranker, x: np.ndarray, contrib: np.ndarray, top: int = 3) -> list[dict[str, Any]]:
    """`x`: one actor's feature vector; `contrib`: its TreeSHAP row (features..., bias). Returns single-feature
    resets, strongest first, then all of them together."""
    index = {f: i for i, f in enumerate(FEATURES)}
    ranked = sorted((f for f in LEVERS if contrib[index[f]] > 0.05), key=lambda f: -contrib[index[f]])[:top]
    out: list[dict[str, Any]] = []
    if not ranked:
        return out
    base = float(ranker.prob(x.reshape(1, -1))[0])
    for f in ranked:
        y = x.copy()
        y[index[f]] = ranker.meta.baseline[f]
        out.append(
            {
                "feature": f,
                "from": round(float(x[index[f]]), 4),
                "to": round(float(ranker.meta.baseline[f]), 4),
                "p_after": round(float(ranker.prob(y.reshape(1, -1))[0]), 4),
            }
        )
    if len(ranked) > 1:
        y = x.copy()
        for f in ranked:
            y[index[f]] = ranker.meta.baseline[f]
        out.append(
            {
                "feature": "+".join(ranked),
                "from": None,
                "to": None,
                "p_after": round(float(ranker.prob(y.reshape(1, -1))[0]), 4),
            }
        )
    for c in out:
        c["p_before"] = round(base, 4)
    return out
