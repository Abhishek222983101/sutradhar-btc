"""E02 enrich - country and ASN for every IP, from the bundled open GeoIP database.

A value already present in the dataset (geo_country / asn columns) is kept alongside as `data_country` so the two
can be compared; the GeoIP answer is what the analyst sees, tagged with its source and date.
"""

from __future__ import annotations

from sutradhar_engine.geoip import AS_OF, SOURCE, lookup
from sutradhar_engine.runner import RunContext, StageReport


class EnrichStage:
    code = "E02"
    name = "geo enrichment"
    requires = ("d_ip",)
    produces = ("ip_geo",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(
            "CREATE TABLE ip_geo (ip VARCHAR PRIMARY KEY, country VARCHAR, asn BIGINT, org VARCHAR, note VARCHAR,"
            " source VARCHAR NOT NULL, as_of VARCHAR NOT NULL)"
        )
        rows = [lookup(ip) for (ip,) in con.execute("SELECT ip FROM d_ip ORDER BY ip").fetchall()]
        if rows:
            con.executemany(
                "INSERT INTO ip_geo VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(r.ip, r.country, r.asn, r.org, r.note, SOURCE, AS_OF) for r in rows],
            )
        located = sum(1 for r in rows if r.country)
        return StageReport(rows={"ip_geo": len(rows), "located": located})


STAGE = EnrichStage()
