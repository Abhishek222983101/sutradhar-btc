"""E07 peel chains - follow "spend, pay a small amount, send the rest onward" hops through the ledger.

A hop is a transaction with one input and two outputs where one output is at least `ratio` times the other. The
larger output is the remainder; the transaction that later spends it continues the chain. Chains of three or
more hops are the classic laundering shape (peeling) and become CHAIN leads.
"""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

HOPS_SQL = """
SELECT t.txid, t.first_seen_us,
       arg_max(o.address, o.sats) AS remainder_addr, max(o.sats) AS big, min(o.sats) AS small
FROM ds.tx t JOIN ds.txout o USING (txid)
WHERE NOT t.is_coinbase AND t.n_in = 1 AND t.n_out = 2
GROUP BY t.txid, t.first_seen_us
HAVING max(o.sats) >= ? * min(o.sats)
"""
SPENDER_SQL = "SELECT address, min(txid) FROM ds.txin GROUP BY address"


class PeelStage:
    code = "E07"
    name = "peel chains"
    requires = ("d_tx",)
    produces = ("peel_chain",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        ratio = ctx.settings.stub_peel_ratio
        hops = {r[0]: r for r in con.execute(HOPS_SQL, [ratio]).fetchall()}
        spender = dict(con.execute(SPENDER_SQL).fetchall())
        nxt = {txid: spender.get(row[2]) for txid, row in hops.items()}
        gap = int(ctx.settings.peel_max_gap_h * 3_600_000_000)
        nxt = {a: b for a, b in nxt.items() if b in hops and b != a and 0 <= hops[b][1] - hops[a][1] <= gap}
        has_prev = set(nxt.values())
        rows, chain_no = [], 0
        for start in sorted(hops):
            if start in has_prev:
                continue
            chain, cur, seen = [], start, set()
            while cur is not None and cur in hops and cur not in seen:
                seen.add(cur)
                chain.append(cur)
                cur = nxt.get(cur)
            if len(chain) >= ctx.settings.peel_min_hops:
                chain_no += 1
                rows += [
                    (f"chain-{chain_no:04d}", i, txid, int(hops[txid][3]), int(hops[txid][1]))
                    for i, txid in enumerate(chain)
                ]
        con.execute(
            "CREATE TABLE peel_chain (chain_id VARCHAR, hop INTEGER, txid VARCHAR, remainder_sats BIGINT, ts_us BIGINT)"
        )
        if rows:
            con.executemany("INSERT INTO peel_chain VALUES (?, ?, ?, ?, ?)", rows)
        return StageReport(rows={"peel_chain": chain_no})


STAGE = PeelStage()
