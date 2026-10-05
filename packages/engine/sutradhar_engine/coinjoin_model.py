"""CoinJoin classifier (E04): which transactions are collaborative equal-output mixes? (Trained in sutradhar_evals.)

A logistic model over structural features of one transaction. Any non-coinbase transaction with at least two
inputs and three outputs is a candidate (a mix needs several participants and several outputs); the model decides.
`RULE_SQL` is the scored heuristic this model replaced. It stays as the evaluation baseline and as the fallback
when no trained weights are bundled.
"""

from __future__ import annotations

FEATURES = (
    "log_n_in",
    "log_n_out",
    "equal_share",
    "n_equal_log",
    "equal_in_ratio",
    "n_equal_values",
    "input_addr_diversity",
    "input_script_homog",
    "output_script_homog",
    "output_value_cv",
    "equal_round",
    "remainder_share",
)

MIN_INPUTS = 2
MIN_OUTPUTS = 3

FEATURE_SQL = """
CREATE OR REPLACE TEMP TABLE coinjoin_feat AS
WITH eq AS (SELECT txid, sats, count(*) AS c FROM ds.txout GROUP BY txid, sats),
grp AS (
  SELECT txid, max(c) AS n_equal, count(*) FILTER (WHERE c >= 2) AS n_equal_values,
         arg_max(sats, c) AS equal_sats
  FROM eq GROUP BY txid
),
ins AS (
  SELECT txid, count(DISTINCT address) AS n_addr, max(sc) AS in_script_max FROM (
    SELECT txid, address, count(*) OVER (PARTITION BY txid, script_type) AS sc FROM ds.txin) GROUP BY txid
),
outs AS (
  SELECT txid, max(sc) AS out_script_max, stddev_pop(sats) / nullif(avg(sats), 0) AS value_cv FROM (
    SELECT txid, sats, count(*) OVER (PARTITION BY txid, script_type) AS sc FROM ds.txout) GROUP BY txid
)
SELECT t.txid, t.n_in, t.n_out,
       ln(t.n_in) AS log_n_in,
       ln(t.n_out) AS log_n_out,
       g.n_equal * 1.0 / t.n_out AS equal_share,
       ln(g.n_equal) AS n_equal_log,
       least(g.n_equal * 1.0 / t.n_in, 3.0) AS equal_in_ratio,
       g.n_equal_values::DOUBLE AS n_equal_values,
       i.n_addr * 1.0 / t.n_in AS input_addr_diversity,
       i.in_script_max * 1.0 / t.n_in AS input_script_homog,
       o.out_script_max * 1.0 / t.n_out AS output_script_homog,
       coalesce(o.value_cv, 0.0) AS output_value_cv,
       (g.equal_sats % 10000 = 0 AND g.n_equal >= 2)::DOUBLE AS equal_round,
       (t.n_out - g.n_equal) * 1.0 / t.n_out AS remainder_share
FROM ds.tx t
JOIN grp g USING (txid) JOIN ins i USING (txid) JOIN outs o USING (txid)
WHERE NOT t.is_coinbase AND t.n_in >= {min_in} AND t.n_out >= {min_out}
"""

# The scored heuristic the trained model replaced; kept as the evaluation baseline and the no-weights fallback.
RULE_SQL = """
CREATE TABLE coinjoin AS
WITH eq AS (SELECT txid, sats, count(*) AS c FROM ds.txout GROUP BY txid, sats),
best AS (SELECT txid, max(c) AS n_equal FROM eq GROUP BY txid)
SELECT t.txid, t.n_in, t.n_out, coalesce(b.n_equal, 1) AS n_equal,
       least(1.0, 0.5 * least(1.0, coalesce(b.n_equal, 1) / 5.0) + 0.3 * least(1.0, t.n_in / 5.0)
                  + 0.2 * (coalesce(b.n_equal, 1) * 1.0 / t.n_out)) AS p
FROM ds.tx t LEFT JOIN best b USING (txid)
WHERE NOT t.is_coinbase AND t.n_in >= 3 AND coalesce(b.n_equal, 1) >= 3
"""
