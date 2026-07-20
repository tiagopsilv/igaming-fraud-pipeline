# exploration/ - one-time data discovery

These scripts are **exploratory data analysis (EDA)** and **design-time analysis** - the work a data
engineer does to *get to know* the data and *decide* the architecture. They are **not part of the
runtime pipeline**: they run once (or ad-hoc), make no promises, and are not orchestrated.

## Why pandas here (and not at scale)
The source files are tiny (~1 MB), so pandas is a fast way to explore. **This does not scale.**
pandas is in-memory and single-core; on large files it would blow up memory. At real volume the same
work is pushed **down into the warehouse**: load the raw data into Bronze first, then profile and
validate with **SQL / dbt** (BigQuery does the heavy lifting, your machine never holds the data).

## What happens to what the exploration finds
Discovery is where findings are *seen the first time*. In the pipeline they become recurring guarantees:

| Finding type | Lives in the pipeline as |
|---|---|
| Type/format fixes (`amount`→NUMERIC, dates, JSON→NDJSON) | ingestion + Bronze `stg_` models |
| Recurring assertions (`ftd ≤ registrations`, no tx before `created_at`, referential integrity) | **dbt tests** |
| Ongoing profiling (null-rate, volume, anomaly, schema drift) | **observability** (dbt-expectations / Elementary) |
| Design conclusions (grain, attribution, fan-out) | **ADRs** + the Silver/Gold models |

New findings keep emerging **as each layer is built** - not all up front. Each layer is also a chance
to hunt for new risks and fraud patterns.

## The scripts
- **`explore_sources.py`** - get to know the base (what each file is, grain, columns) + a 7-step
  investigation of quality and coherence.
- **`arch_discovery.py`** - Kimball questions that shape the star schema (grain, dimensions, SCD, fan-out).
- **`compare_attribution.py`** - compares affiliate attribution rules; the basis of ADR-0004.
- **`explore_ingestion.py`** - discovery pass over what the ingestion must handle (encoding, CRLF,
  embedded newlines, nesting, column-name validity, volume); the basis of ADR-0005.
- **`explore_contract.py`** - the data contract: grain per table, timezone, and the definitions of
  "account" and "fraud"; the basis of ADR-0006.
- **`explore_star_schema.py`** - justifies the Gold star schema: dimensions vs facts, grain, and the
  BigQuery physical design (partition/cluster/materialization); the basis of ADR-0007.
- **`explore_load_strategy.py`** - justifies the load strategy per source (watermark / unique key /
  change-tracking → full vs incremental); the basis of ADR-0008.
- **`explore_nfr.py`** - derives the non-functional targets from the data (freshness from timestamp
  granularity, quality SLOs from the measured baseline, cost from volume); the basis of ADR-0009.

Run any of them with `python exploration/<script>.py`.
