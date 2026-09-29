"""E13 taint - propagate risk from seed (watchlisted) wallets through the ledger with the haircut rule.

Each transaction's outputs inherit the tainted share of its inputs' value (value-weighted), so risk thins out
as funds are split and mixed with clean money. Seeds come from `watchlist.csv` beside the dataset, if present.
A cluster's taint is the highest taint of any of its addresses.
"""

from __future__ import annotations

import csv
from collections import defaultdict

from sutradhar_engine.runner import RunContext, StageReport

TX_SQL = """
SELECT t.txid, list(i.address ORDER BY i.idx), list(i.sats ORDER BY i.idx)
FROM ds.tx t JOIN ds.txin i USING (txid) GROUP BY t.txid, t.first_seen_us ORDER BY t.first_seen_us, t.txid
"""
OUT_SQL = "SELECT txid, address, sats FROM ds.txout ORDER BY txid, idx"


class TaintStage:
    code = "E13"
    name = "risk propagation"
    requires = ("cluster",)
    produces = ("taint",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        seeds: dict[str, tuple[float, str]] = {}
        path = ctx.dataset_path.parent / "watchlist.csv"
        if path.exists():
            with path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    seeds[row["address"].strip()] = (
                        float(row.get("confidence") or 1),
                        row.get("category", "other"),
                    )
        taint = {a: c for a, (c, _) in seeds.items()}
        outs = defaultdict(list)
        for txid, address, sats in con.execute(OUT_SQL).fetchall():
            outs[txid].append((address, sats))
        for txid, addrs, sats in con.execute(TX_SQL).fetchall():
            total = sum(sats)
            share = (
                sum(taint.get(a, 0.0) * s for a, s in zip(addrs, sats, strict=True)) / total if total else 0.0
            )
            if share > 0.001:
                for address, _ in outs[txid]:
                    taint[address] = max(taint.get(address, 0.0), share)
        con.execute(
            "CREATE TABLE taint (address VARCHAR PRIMARY KEY, taint DOUBLE NOT NULL, is_seed BOOLEAN NOT NULL)"
        )
        if taint:
            con.executemany(
                "INSERT INTO taint VALUES (?, ?, ?)", [(a, t, a in seeds) for a, t in sorted(taint.items())]
            )
        return StageReport(rows={"taint": len(taint)}, notes=[f"{len(seeds)} seed address(es)"])


STAGE = TaintStage()
