# ADR-0005 - Raw ingestion: idempotent NDJSON load into a `raw` dataset

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `exploration/explore_ingestion.py` - a dedicated detective pass over what the load
  must handle. It finds: the JSON files are pretty-printed **arrays** (need NDJSON); the sources are
  **CRLF** (so the loader must write LF); the JSON is **flat with a single schema** and the CSVs have
  **no ragged rows or embedded newlines** (a clean autodetect load); all column names are **valid**
  and do **not collide** with the audit columns; and the **volume baseline** is 600/4000/1800/2000.

## Context
Four heterogeneous source files (JSON arrays + CSV) must land in BigQuery so the Bronze `stg_` models
can read them. BigQuery only accepts JSON as NDJSON, and the load must be safe to rerun (retries,
reprocessing) without duplicating data.

## Decision
An ingestion step (`ingestion/load_raw.py`) normalizes each source to **NDJSON**, adds two audit
columns (`_ingested_at`, `_source_file`), and loads it into a `raw` dataset with **`WRITE_TRUNCATE`**
(atomic, idempotent). `raw` mirrors the sources 1:1 - no business logic. Configuration lives in a
**committed, public `config.toml`** (project, dataset, location, source dir, keyfile *path*) so a
fresh clone runs with no setup; every value is overridable by an env var for CI/production. The only
secret - the service-account JSON - stays gitignored. Loads target **native tables** (not external
tables) because the data is queried repeatedly downstream.

The exploration scripts run **fully offline** from the committed sample (no GCP), and the loader has
an `OTG_SKIP_LOAD=1` mode that does the NDJSON conversion without touching BigQuery - so discovery
and the conversion step always run even when the warehouse is unreachable.

## Considered options
- **External tables over GCS** - no load step, near-real-time, but slower per-query; rejected because
  models and the dashboard hit this data repeatedly.
- **dbt seeds** - rejected: seeds are for small static reference data, not raw/source data.

## Consequences
- Reruns and retries are safe (WRITE_TRUNCATE recreates each table atomically).
- The repo is reproducible (a small synthetic sample lives in `data/`); in production the landing
  zone is a GCS bucket and the same script reads from there (config-driven) - no code change.
- `raw` stays faithful to the sources; all casting and business rules happen from Bronze onward.
- At real scale, the JSON→NDJSON conversion would stream (or the data would already land as NDJSON in GCS).
