"""Change-address model: which output of a payment goes back to the sender? (Trained in sutradhar_evals.)"""

from __future__ import annotations

FEATURES = (
    "same_script",
    "fresh_addr",
    "single_use",
    "value_rank",
    "frac_of_input",
    "round_amount",
    "n_out",
    "position",
)

FEATURE_SQL = """
CREATE OR REPLACE TEMP TABLE change_feat AS
WITH first_out AS (SELECT txid, count(*) AS n_out FROM ds.txout GROUP BY txid),
in_script AS (SELECT txid, mode(script_type) AS s FROM ds.txin GROUP BY txid),
appearances AS (
  SELECT address, count(*) AS n_out_appearances, min(t.first_seen_us) AS first_us
  FROM ds.txout o JOIN ds.tx t USING (txid) GROUP BY address
),
in_use AS (SELECT address, count(*) AS n_in_appearances, min(t.first_seen_us) AS first_in_us
           FROM ds.txin i JOIN ds.tx t USING (txid) GROUP BY address)
SELECT o.txid, o.idx,
       (o.script_type = s.s)::DOUBLE AS same_script,
       (a.first_us >= t.first_seen_us AND coalesce(u.first_in_us, 9223372036854775807) >= t.first_seen_us)::DOUBLE AS fresh_addr,
       (a.n_out_appearances = 1)::DOUBLE AS single_use,
       (rank() OVER (PARTITION BY o.txid ORDER BY o.sats) - 1) * 1.0 / greatest(1, f.n_out - 1) AS value_rank,
       o.sats * 1.0 / nullif(t.in_sats, 0) AS frac_of_input,
       (o.sats % 10000 = 0)::DOUBLE AS round_amount,
       f.n_out::DOUBLE AS n_out,
       o.idx * 1.0 / greatest(1, f.n_out - 1) AS position
FROM ds.txout o
JOIN ds.tx t USING (txid) JOIN first_out f USING (txid) JOIN in_script s USING (txid)
JOIN appearances a ON a.address = o.address LEFT JOIN in_use u ON u.address = o.address
WHERE NOT t.is_coinbase AND f.n_out BETWEEN 2 AND 4
  AND t.txid NOT IN (SELECT txid FROM coinjoin WHERE p >= 0.5)
"""
