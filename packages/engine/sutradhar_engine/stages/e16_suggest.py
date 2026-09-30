"""E16 merge suggestions - pairs of wallet clusters that may belong to one operator, with reasons.

Candidates come from co-origin (a shared IP). Score = 0.6 * co-origin strength + 0.25 * graph-embedding similarity +
0.15 * fingerprint similarity. Suggestions are for an analyst to accept or reject; nothing is merged automatically.
"""

from __future__ import annotations

import json
import math

import numpy as np

from sutradhar_engine.runner import RunContext, StageReport

TOP = 200


def _cos(a: list[float], b: list[float]) -> float:
    x, y = np.array(a), np.array(b)
    d = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(x @ y / d) if d else 0.0


class SuggestStage:
    code = "E16"
    name = "merge suggestions"
    requires = ("co_origin",)
    produces = ("merge_suggestion",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(
            "CREATE TABLE merge_suggestion (a VARCHAR, b VARCHAR, score DOUBLE NOT NULL, reasons VARCHAR NOT NULL, PRIMARY KEY (a, b))"
        )
        have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        emb = (
            dict(con.execute("SELECT cluster_id, vec FROM embedding").fetchall())
            if "embedding" in have
            else {}
        )
        fp = (
            dict(con.execute("SELECT cluster_id, vec FROM fingerprint").fetchall())
            if "fingerprint" in have
            else {}
        )
        out = []
        for a, b, ips, tx in con.execute("SELECT a, b, shared_ips, shared_tx FROM co_origin").fetchall():
            strength = 1 - math.exp(-tx / 2)
            e = max(0.0, _cos(emb[a], emb[b])) if a in emb and b in emb else 0.0
            f = max(0.0, _cos(fp[a], fp[b])) if a in fp and b in fp else 0.0
            score = 0.6 * strength + 0.25 * e + 0.15 * f
            reasons = [
                f"{ips} shared origin IP(s) covering {tx} transaction(s)",
                *([f"graph neighbourhood similarity {e:.2f}"] if a in emb and b in emb else []),
                *([f"behaviour similarity {f:.2f}"] if a in fp and b in fp else []),
            ]
            out.append((a, b, round(score, 4), json.dumps(reasons)))
        out.sort(key=lambda r: (-r[2], r[0], r[1]))
        if out:
            con.executemany("INSERT INTO merge_suggestion VALUES (?, ?, ?, ?)", out[:TOP])
        return StageReport(rows={"merge_suggestion": min(len(out), TOP)})


STAGE = SuggestStage()
