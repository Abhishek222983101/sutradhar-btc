"""E05 cluster - common-input-ownership clustering with a CoinJoin guard (I8).

Addresses spent together in one transaction are one wallet, except in transactions that look like CoinJoins
(many inputs and several equal-valued outputs), which are skipped so unrelated people are never merged.
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

CJ_MIN_INPUTS = 3
CJ_MIN_EQUAL_OUTPUTS = 3

TXS_SQL = """
SELECT i.txid, list(i.address ORDER BY i.idx) AS addrs,
       (SELECT max(c) FROM (SELECT count(*) c FROM ds.txout o WHERE o.txid = i.txid GROUP BY o.sats)) AS equal_outs
FROM ds.txin i GROUP BY i.txid
"""


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
    requires = ("d_tx",)
    produces = ("cluster",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        uf, skipped = _UnionFind(), 0
        for _txid, addrs, equal_outs in con.execute(TXS_SQL).fetchall():
            for a in addrs:
                uf.find(a)
            if len(addrs) >= CJ_MIN_INPUTS and (equal_outs or 0) >= CJ_MIN_EQUAL_OUTPUTS:
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
