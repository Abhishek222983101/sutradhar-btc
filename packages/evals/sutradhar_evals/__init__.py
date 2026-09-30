"""Sutradhar evaluation harness: reads ground truth (I7 boundary — the engine never imports this package)."""

__version__ = "0.1.0"

from sutradhar_evals.metrics import (
    ClusterMetrics,
    EvalReport,
    OriginMetrics,
    WorldRun,
    build_world,
    cluster_purity,
    evaluate,
    origin_accuracy,
)

__all__ = [
    "ClusterMetrics",
    "EvalReport",
    "OriginMetrics",
    "WorldRun",
    "build_world",
    "cluster_purity",
    "evaluate",
    "origin_accuracy",
]
