# Dataset

The problem statement provides no data, so the dataset is generated (`sutradhar gen run`). Every value is synthetic.

## Fields

Required by the PS, always present in generated data:

| Field | Meaning |
|---|---|
| `timestamp` | When a sensor logged the announcement (UTC, microseconds internally) |
| `src_ip`, `src_port` | The peer that announced the transaction |
| `dst_ip`, `dst_port` | The listening sensor that received it |
| `txid` | Transaction id (64 hex characters) |
| `input_addresses[]`, `input_amounts[]` | Spent addresses and their amounts (BTC in files, integer satoshis inside) |
| `output_addresses[]`, `output_amounts[]` | Receiving addresses and amounts |
| `geo_country`, `asn` | Country and autonomous system of the source (generated from DB-IP blocks) |

Optional: `fee` (computed when absent), `script_type` (inferred from the address when absent).

Formats: CSV, TSV, JSON (array of records), NDJSON, XML (`<records><record>…`). Arrays are JSON lists in CSV cells, native
lists in JSON, repeated child elements in XML. All formats normalise to identical data (tested). Files with other
column names: `sutradhar ingest FILE --auto-map`.

## Scenarios

| Scenario | What it contains |
|---|---|
| `tiny` | About 220 transactions, ransomware story, documentation-range IPs. For tests. |
| `demo` | Same economy with public-looking IPs and countries. |
| `rich` | 160 users over 5 days: ransomware with a peeling chain, a CoinJoin coordinator, a darknet market with vendors and cash-outs. |

Generation is deterministic: the same scenario and seed produce byte-identical files.

## Ground truth

`worlds/<x>/truth/*.parquet`: true origin node and IP per transaction, wallet ownership per address, change outputs, peel
hops, agent roles. Only `packages/evals` reads these files; an import rule in CI keeps the engine from importing it.
