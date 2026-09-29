"""E01 load — freeze the run's view of the dataset: dense integer dictionaries and the capability profile."""

from __future__ import annotations

from sutradhar_engine.runner import RunContext, StageReport

_COUNTS = {
    "d_tx": "SELECT count(*) FROM d_tx",
    "d_addr": "SELECT count(*) FROM d_addr",
    "d_ip": "SELECT count(*) FROM d_ip",
}


class LoadStage:
    code = "E01"
    name = "load"
    requires = ("d_tx", "d_addr", "d_ip", "run_meta")
    produces = ("d_tx", "d_addr", "d_ip")

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(
            "INSERT INTO d_tx SELECT (row_number() OVER (ORDER BY txid) - 1)::INTEGER, txid FROM ds.tx"
        )
        con.execute(
            """
            INSERT INTO d_addr
            SELECT (row_number() OVER (ORDER BY address) - 1)::INTEGER, address, min(script_type)
            FROM (SELECT address, script_type FROM ds.txin UNION ALL SELECT address, script_type FROM ds.txout)
            GROUP BY address
            """
        )
        con.execute(
            """
            INSERT INTO d_ip
            SELECT (row_number() OVER (ORDER BY ip) - 1)::INTEGER, ip
            FROM (SELECT src_ip AS ip FROM ds.obs UNION SELECT dst_ip FROM ds.obs)
            WHERE ip IS NOT NULL
            """
        )
        ctx.put_meta("capability", ctx.capability.model_dump(mode="json"))
        ctx.put_meta("dataset_manifest", ctx.dataset_manifest)
        counts = {}
        for name, sql in _COUNTS.items():
            row = con.execute(sql).fetchone()
            counts[name] = 0 if row is None else int(row[0])
        return StageReport(rows=counts)


STAGE = LoadStage()
