"""Build docs/EVAL.json (and .md): the numbers the web app and README quote, computed fresh, never hand-typed."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from sutradhar_evals.metrics import evaluate
from sutradhar_gen.config import PRESETS

DOCS = Path(__file__).resolve().parents[3] / "docs"
SEEDS = (1, 2, 3, 4, 5)


def main(scenario: str = "rich", out_dir: Path = DOCS, seeds: tuple[int, ...] = SEEDS) -> dict:
    import tempfile

    reports = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in seeds:
            reports.append(evaluate(PRESETS[scenario], seed, Path(tmp) / f"seed{seed}"))
    top1 = [r.origin.top1_accuracy for r in reports]
    top3 = [r.origin.top3_accuracy for r in reports]
    baseline = [r.origin.random_baseline for r in reports]
    purity = [r.cluster.purity for r in reports]
    cj = [r.coinjoin for r in reports if r.coinjoin.truth_coinjoins]
    summary = {
        "scenario": scenario,
        "seeds": list(seeds),
        "runs": [r.to_dict() for r in reports],
        "origin_top1_mean": round(statistics.mean(top1), 4),
        "origin_top1_stdev": round(statistics.pstdev(top1), 4) if len(top1) > 1 else 0.0,
        "origin_top3_mean": round(statistics.mean(top3), 4),
        "origin_ceiling_mean": round(statistics.mean(r.origin.ceiling for r in reports), 4),
        "origin_first_spy_mean": round(statistics.mean(r.origin.first_spy_top1 for r in reports), 4),
        "peel_precision_mean": round(statistics.mean(r.peel.precision for r in reports), 4),
        "peel_lead_precision_mean": round(statistics.mean(r.peel.lead_precision for r in reports), 4),
        "peel_recall_mean": round(statistics.mean(r.peel.recall for r in reports), 4),
        "suggest_precision_mean": round(statistics.mean(r.suggest.precision_top50 for r in reports), 4),
        "suggest_random_rate_mean": round(statistics.mean(r.suggest.random_pair_rate for r in reports), 6),
        **{
            f"ranker_{variant}_{k}_mean": round(
                statistics.mean(getattr(getattr(r, attr), k) for r in reports), 4
            )
            for variant, attr in (("seeded", "ranker"), ("blind", "ranker_blind"))
            for k in (
                "pr_auc",
                "taint_only_pr_auc",
                "r_precision",
                "recall_at_20",
                "ece",
                "country_ablation_delta",
                "prevalence",
            )
        },
        "origin_random_baseline_mean": round(statistics.mean(baseline), 4),
        "wallet_cluster_purity_mean": round(statistics.mean(purity), 4),
        "observable_transactions_total": sum(r.origin.observable_transactions for r in reports),
        "coinjoin_precision_mean": round(statistics.mean(c.precision for c in cj), 4) if cj else None,
        "coinjoin_recall_mean": round(statistics.mean(c.recall for c in cj), 4) if cj else None,
        "coinjoins_evaluated": sum(c.truth_coinjoins for c in cj),
        "change_argmax_accuracy_mean": round(statistics.mean(r.change.argmax_accuracy for r in reports), 4),
        "change_merge_precision_mean": round(statistics.mean(r.change.merge_precision for r in reports), 4),
        "change_merge_links_total": sum(r.change.merge_links for r in reports),
        "purity_if_coinjoins_merged_mean": round(
            statistics.mean(r.purity_if_coinjoins_merged for r in reports), 4
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EVAL.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Evaluation results",
        "",
        f"Computed by `uv run sutradhar evals report`, scenario `{scenario}`, seeds {list(seeds)}. Not hand-typed —",
        "re-run the command to reproduce every number below against freshly generated worlds with hidden ground truth.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Origin IP found, first try (top-1) | **{summary['origin_top1_mean']:.1%}** (± {summary['origin_top1_stdev']:.1%} across seeds) |",
        f"| Origin IP in top 3 candidates | **{summary['origin_top3_mean']:.1%}** |",
        f"| Ceiling: true origin announced to a sensor at all | {summary['origin_ceiling_mean']:.1%} |",
        f'| Baseline: earliest announcer wins ("first-spy") | {summary["origin_first_spy_mean"]:.1%} |',
        f"| Baseline: random guess among announcers | {summary['origin_random_baseline_mean']:.1%} |",
        f"| Wallet cluster purity vs. hidden truth | **{summary['wallet_cluster_purity_mean']:.1%}** |",
        f"| Observable transactions evaluated | {summary['observable_transactions_total']} |",
    ]
    if summary["coinjoins_evaluated"]:
        lines += [
            f"| CoinJoin detection precision / recall | **{summary['coinjoin_precision_mean']:.1%}** / **{summary['coinjoin_recall_mean']:.1%}** ({summary['coinjoins_evaluated']} CoinJoins) |",
            f"| Cluster purity if CoinJoins were merged (ablation) | {summary['purity_if_coinjoins_merged_mean']:.1%} |",
        ]
    lines += [
        f"| Peel-chain hops: precision / recall | {summary['peel_precision_mean']:.1%} / {summary['peel_recall_mean']:.1%} (published CHAIN leads that are real chains: {summary['peel_lead_precision_mean']:.1%}) |",
        f"| Merge suggestions (top 50): same operator | {summary['suggest_precision_mean']:.1%} (random pairs: {summary['suggest_random_rate_mean']:.2%}) |",
        f"| Lead ranker PR-AUC, with watchlist seeds / without | **{summary['ranker_seeded_pr_auc_mean']:.3f}** / **{summary['ranker_blind_pr_auc_mean']:.3f}** |",
        f"| Baseline: taint alone, PR-AUC with seeds / without | {summary['ranker_seeded_taint_only_pr_auc_mean']:.3f} / {summary['ranker_blind_taint_only_pr_auc_mean']:.3f} |",
        f"| Illicit actors ranked first (R-precision), with seeds / without | {summary['ranker_seeded_r_precision_mean']:.1%} / {summary['ranker_blind_r_precision_mean']:.1%} (illicit share of actors: {summary['ranker_seeded_prevalence_mean']:.1%}) |",
        f"| Illicit actors found in the top 20, with seeds / without | {summary['ranker_seeded_recall_at_20_mean']:.1%} / {summary['ranker_blind_recall_at_20_mean']:.1%} |",
        f"| Calibration error (ECE), with / without seeds | {summary['ranker_seeded_ece_mean']:.3f} / {summary['ranker_blind_ece_mean']:.3f} |",
        f"| Stability: PR-AUC change when the country feature is removed | {summary['ranker_seeded_country_ablation_delta_mean']:+.4f} |",
        f"| Change output identified (per transaction) | **{summary['change_argmax_accuracy_mean']:.1%}** |",
        f"| Change links used for clustering: precision | **{summary['change_merge_precision_mean']:.1%}** ({summary['change_merge_links_total']} links) |",
        "",
        "## Per-seed detail",
        "",
        "| Seed | Top-1 | Top-3 | Baseline | Clusters | Purity |",
        "|---|---|---|---|---|---|",
    ]
    for r in reports:
        lines.append(
            f"| {r.seed} | {r.origin.top1_accuracy:.1%} | {r.origin.top3_accuracy:.1%} | {r.origin.random_baseline:.1%} "
            f"| {r.cluster.clusters} | {r.cluster.purity:.1%} |"
        )
    lines.append("")
    (out_dir / "EVAL.md").write_text("\n".join(lines), encoding="utf-8")
    api_copy = DOCS.parent / "apps/api/sutradhar_api/demo/eval.json"
    if out_dir == DOCS and api_copy.parent.exists():
        api_copy.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
