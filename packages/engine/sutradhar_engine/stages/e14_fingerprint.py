"""E14 fingerprints - how a wallet cluster behaves, as a standardised vector.

Median fee rate, typical payment size, output count, script-type mix and time-of-day activity. Two clusters run by
the same operator tend to look alike; the vector is one input to merge suggestions.
"""

from __future__ import annotations

import numpy as np

from sutradhar_engine.runner import RunContext, StageReport

SQL = """
SELECT c.cluster_id, t.txid, t.fee_sats * 1.0 / (68 * t.n_in + 31 * t.n_out + 11) AS feerate,
       ln(1 + t.in_sats) AS log_value, t.n_out, t.first_seen_us
FROM ds.tx t JOIN (SELECT i.txid, min(c.cluster_id) AS cluster_id FROM ds.txin i JOIN cluster c USING (address) GROUP BY i.txid) c
  USING (txid) WHERE NOT t.is_coinbase AND t.n_in > 0
"""
SCRIPTS_SQL = """
SELECT c.cluster_id, o.script_type, count(*) FROM ds.txout o JOIN cluster c USING (address) GROUP BY 1, 2
"""
KINDS = ("p2wpkh", "p2tr", "p2pkh", "p2sh", "p2wsh")
MIN_TX = 3


class FingerprintStage:
    code = "E14"
    name = "behavioural fingerprints"
    requires = ("cluster",)
    produces = ("fingerprint",)

    def run(self, ctx: RunContext) -> StageReport:
        con = ctx.con
        con.execute(
            "CREATE TABLE fingerprint (cluster_id VARCHAR PRIMARY KEY, n_tx INTEGER NOT NULL, vec DOUBLE[] NOT NULL)"
        )
        rows: dict[str, list[tuple]] = {}
        for r in con.execute(SQL).fetchall():
            rows.setdefault(r[0], []).append(r)
        mix: dict[str, dict[str, int]] = {}
        for cid, kind, n in con.execute(SCRIPTS_SQL).fetchall():
            mix.setdefault(cid, {})[kind] = int(n)
        ids = sorted(c for c, v in rows.items() if len(v) >= MIN_TX)
        if not ids:
            return StageReport(rows={"fingerprint": 0})
        feats = []
        for cid in ids:
            v = rows[cid]
            hours = np.array([(x[5] // 3_600_000_000) % 24 for x in v])
            total = sum(mix.get(cid, {}).values()) or 1
            feats.append(
                [
                    float(np.median([x[2] for x in v])),
                    float(np.median([x[3] for x in v])),
                    float(np.mean([x[4] for x in v])),
                    *[mix.get(cid, {}).get(k, 0) / total for k in KINDS],
                    *[float(np.mean((hours // 6) == b)) for b in range(4)],
                ]
            )
        arr = np.array(feats)
        sd = arr.std(axis=0)
        sd[sd == 0] = 1.0
        z = (arr - arr.mean(axis=0)) / sd
        con.executemany(
            "INSERT INTO fingerprint VALUES (?, ?, ?)",
            [(c, len(rows[c]), [float(x) for x in z[i]]) for i, c in enumerate(ids)],
        )
        return StageReport(rows={"fingerprint": len(ids)})


STAGE = FingerprintStage()
