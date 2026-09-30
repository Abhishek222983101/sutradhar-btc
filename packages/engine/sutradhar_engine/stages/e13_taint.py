"""E13 taint - propagate risk from seed (watchlisted) wallets through the ledger with the haircut rule.

Each transaction's outputs inherit the tainted share of its inputs' value (value-weighted), so risk thins out as
funds are split and mixed with clean money. Two refinements keep it honest:
  * hop decay: every hop multiplies the propagated share by `taint_hop_decay`;
  * service stop: taint that reaches a service (exchange, batch payer) is recorded there but goes no further, because
    a service mixes everyone's funds and passing risk through it would tar its whole customer base.
Seeds come from the run's frozen `seeds.csv` (else `watchlist.csv` beside the dataset).
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
SERVICE_ADDR_SQL = "SELECT c.address FROM cluster c JOIN service s USING (cluster_id)"


Tx = tuple[
    str, list[str], list[int], list[tuple[str, int]]
]  # txid, input addresses, input sats, outputs (address, sats)


def propagate(
    txs: list[Tx], seeds: dict[str, tuple[float, str]], service_addrs: set[str], decay: float
) -> tuple[dict[str, float], dict[str, int], int]:
    """Haircut taint over transactions given in time order. Returns (taint per address, hops per address, arrivals that
    stopped at a service). Pure, so it can be property-tested."""
    taint = {a: c for a, (c, _) in seeds.items()}
    hops = dict.fromkeys(seeds, 0)
    stopped = 0
    for _txid, addrs, sats, outs in txs:
        total = sum(sats)
        if not total:
            continue
        live = [
            (a, s) for a, s in zip(addrs, sats, strict=True) if a not in service_addrs
        ]  # the service stop
        share = sum(taint.get(a, 0.0) * s for a, s in live) / total
        if share <= 0.001:
            continue
        hop = min((hops[a] for a, _ in live if taint.get(a, 0.0) > 0), default=0) + 1
        share *= decay**hop
        for address, _ in outs:
            if share > taint.get(address, 0.0):
                taint[address] = share
                hops[address] = 0 if address in seeds else hop  # a seed is always step zero
                stopped += address in service_addrs
    return taint, hops, stopped


def load_seeds(ctx: RunContext) -> dict[str, tuple[float, str]]:
    run_seeds = ctx.run_dir / "seeds.csv"
    path = run_seeds if run_seeds.exists() else ctx.dataset_path.parent / "watchlist.csv"
    seeds: dict[str, tuple[float, str]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                seeds[row["address"].strip()] = (
                    float(row.get("confidence") or 1),
                    row.get("category", "other"),
                )
    return seeds


class TaintStage:
    code = "E13"
    name = "risk propagation"
    requires = ("cluster", "service")
    produces = ("taint",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        seeds = load_seeds(ctx)
        service_addrs = {r[0] for r in con.execute(SERVICE_ADDR_SQL).fetchall()}
        outs = defaultdict(list)
        for txid, address, sats in con.execute(OUT_SQL).fetchall():
            outs[txid].append((address, int(sats)))
        txs = [
            (txid, addrs, [int(x) for x in sats], outs[txid])
            for txid, addrs, sats in con.execute(TX_SQL).fetchall()
        ]
        taint, hops, stopped = propagate(txs, seeds, service_addrs, ctx.settings.taint_hop_decay)
        con.execute(
            "CREATE TABLE taint (address VARCHAR PRIMARY KEY, taint DOUBLE NOT NULL, is_seed BOOLEAN NOT NULL,"
            " hops INTEGER NOT NULL, category VARCHAR)"
        )
        if taint:
            con.executemany(
                "INSERT INTO taint VALUES (?, ?, ?, ?, ?)",
                [
                    (a, t, a in seeds, hops.get(a, 0), seeds[a][1] if a in seeds else None)
                    for a, t in sorted(taint.items())
                ],
            )
        return StageReport(
            rows={"taint": len(taint)},
            notes=[f"{len(seeds)} seed address(es)", f"{stopped} taint arrival(s) stopped at services"],
        )


STAGE = TaintStage()
