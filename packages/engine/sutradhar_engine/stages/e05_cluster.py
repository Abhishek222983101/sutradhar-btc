"""E05 cluster - common-input-ownership clustering with a CoinJoin guard (I8).

Addresses spent together in one transaction are one wallet, except in transactions that look like CoinJoins
(many inputs and several equal-valued outputs), which are skipped so unrelated people are never merged.
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

TXS_SQL = "SELECT i.txid, list(i.address ORDER BY i.idx) AS addrs FROM ds.txin i GROUP BY i.txid"
CJ_SQL = "SELECT txid FROM coinjoin WHERE p >= ?"


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


class ClusterStage:
    code = "E05"
    name = "wallet clustering"
    requires = ("coinjoin",)
    produces = ("cluster",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        uf, skipped = _UnionFind(), 0
        flagged = {r[0] for r in con.execute(CJ_SQL, [ctx.settings.coinjoin_min_p]).fetchall()}
        for txid, addrs in con.execute(TXS_SQL).fetchall():
            for a in addrs:
                uf.find(a)
            if txid in flagged:  # I8: never merge the inputs of a CoinJoin
                skipped += 1
                continue
            for a in addrs[1:]:
                uf.union(addrs[0], a)
        rows = sorted((a, uf.find(a)) for a in uf.parent)
        con.execute("CREATE TABLE cluster (address VARCHAR PRIMARY KEY, cluster_id VARCHAR NOT NULL)")
        if rows:
            con.executemany("INSERT INTO cluster VALUES (?, ?)", rows)
        n = len({c for _, c in rows})
        return StageReport(rows={"cluster": n}, notes=[f"{skipped} CoinJoin-shaped transactions excluded"])


STAGE = ClusterStage()
