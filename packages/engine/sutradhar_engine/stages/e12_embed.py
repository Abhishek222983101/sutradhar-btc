"""E12 embeddings - a 16-dimensional vector per wallet cluster from the flow graph (truncated SVD).

Clusters that move money to and from the same neighbours end up close together. The vectors feed merge suggestions.
Deterministic: the SVD start vector is seeded and each component's sign is fixed.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import svds

from sutradhar_engine.runner import RunContext, StageReport

DIMS = 16
MIN_CLUSTERS = 24
DENSE_MAX = 1500


class EmbedStage:
    code = "E12"
    name = "graph embeddings"
    requires = ("flow",)
    produces = ("embedding",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute("CREATE TABLE embedding (cluster_id VARCHAR PRIMARY KEY, vec DOUBLE[] NOT NULL)")
        ids = [
            r[0]
            for r in con.execute(
                "SELECT DISTINCT c FROM (SELECT src AS c FROM flow UNION SELECT dst FROM flow) ORDER BY c"
            ).fetchall()
        ]
        if len(ids) < MIN_CLUSTERS:
            return StageReport(rows={"embedding": 0}, notes=["too few connected clusters to embed"])
        index = {c: i for i, c in enumerate(ids)}
        edges = con.execute("SELECT src, dst, sats FROM flow").fetchall()
        rows = [index[a] for a, _, _ in edges] + [index[b] for _, b, _ in edges]
        cols = [index[b] for _, b, _ in edges] + [index[a] for a, _, _ in edges]
        w = np.log1p(np.array([s for _, _, s in edges] * 2, dtype=float))
        adj = sp.csr_matrix((w, (rows, cols)), shape=(len(ids), len(ids)))
        deg = np.asarray(adj.sum(axis=1)).ravel()
        deg[deg == 0] = 1.0
        norm = sp.diags(1 / np.sqrt(deg)) @ adj @ sp.diags(1 / np.sqrt(deg))
        k = min(DIMS, len(ids) - 2)
        try:
            if len(ids) <= DENSE_MAX:  # exact and deterministic for small graphs
                u, sv, _ = np.linalg.svd(norm.toarray(), full_matrices=False)
                u, sv = u[:, :k], sv[:k]
            else:
                v0 = np.random.default_rng(ctx.settings.seed).standard_normal(len(ids))
                u, sv, _ = svds(norm.astype(float), k=k, v0=v0)
        except Exception as exc:  # a stage must not take the run down; embeddings only refine suggestions
            return StageReport(rows={"embedding": 0}, notes=[f"embedding skipped: {type(exc).__name__}"])
        vec = u * np.sqrt(sv)
        for j in range(vec.shape[1]):
            if vec[np.argmax(np.abs(vec[:, j])), j] < 0:
                vec[:, j] = -vec[:, j]
        vec = vec[:, np.argsort(-sv)]
        con.executemany(
            "INSERT INTO embedding VALUES (?, ?)", [(c, [float(x) for x in vec[i]]) for c, i in index.items()]
        )
        return StageReport(rows={"embedding": len(ids)}, notes=[f"{vec.shape[1]} dimensions"])


STAGE = EmbedStage()
