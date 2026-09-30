"""Turn feature contributions into plain-language reasons, using templates.yaml and the language guard."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from sutradhar_engine.actor_model import FEATURE_FAMILY
from sutradhar_engine.explain.guard import check_reason, check_summary

TEMPLATES = Path(__file__).parent / "templates.yaml"


@lru_cache(maxsize=1)
def templates() -> dict[str, dict[str, str]]:
    data = yaml.safe_load(TEMPLATES.read_text(encoding="utf-8"))
    missing = set(FEATURE_FAMILY) - set(data)
    if missing:
        raise ValueError(f"no explanation template for {sorted(missing)}")
    return data


def _hours(h: float) -> str:
    if h < 1:
        return f"{h * 60:.0f} minutes"
    return f"{h:.1f} hours" if h < 48 else f"{h / 24:.1f} days"


_FORMATTERS = {
    "pct": lambda v: f"{v * 100:.0f}%",
    "count": lambda v: f"{v:.0f}",
    "hops": lambda v: f"{v:.0f}",
    "num": lambda v: f"{v:.1f}",
    "log_count": lambda v: f"{math.expm1(v):.0f}",
    "log_btc": lambda v: f"{math.expm1(v) / 100:.2f}",
    "log_hours": lambda v: _hours(math.expm1(v)),
    "score": lambda v: f"{v:.1f}",
    "bool": lambda v: "yes" if v >= 0.5 else "no",
}


def fmt_value(kind: str, value: float) -> str:
    return _FORMATTERS.get(kind, lambda v: f"{v:g}")(value)


def render_reason(feature: str, value: float, contribution: float) -> dict[str, Any] | None:
    """One reason as stored on a lead, or None if the template has no text for this direction."""
    t = templates()[feature]
    text = t.get("up" if contribution >= 0 else "down")
    if not text:
        return None
    text = text.format(value=fmt_value(t["fmt"], value))
    check_reason(text)
    return {
        "family": FEATURE_FAMILY[feature],
        "feature": feature,
        "label": t["label"],
        "value": round(float(value), 4),
        "contribution": round(float(contribution), 4),
        "text": text,
    }


def hedged_summary(title_core: str, n_families: int) -> str:
    text = (
        f"Evidence suggests {title_core}. It comes from {n_families} independent kind(s) of evidence and is a lead for "
        "review, not a finding about anyone."
    )
    check_summary(text)
    return text
