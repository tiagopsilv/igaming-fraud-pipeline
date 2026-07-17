# ingestion/ - landing the raw data into BigQuery

The ingestion layer normalizes the four source files and loads them, untouched by business logic,
into a `raw` dataset in BigQuery. The Bronze `stg_` models read `raw` via `source()`.

```
data/ (sample; prod: GCS)  →  load_raw.py  →  raw.<table> in BigQuery  →  Bronze staging
```

## Design decisions (and why)
- **NDJSON, native load.** BigQuery only accepts JSON as NDJSON, so each source is normalized to
  newline-delimited JSON first. We load into **native tables** (not external tables) because the data
  is queried repeatedly by models and the dashboard - external tables suit occasional queries.
  ([BigQuery: loading JSON](https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-json),
  [external tables](https://cloud.google.com/bigquery/docs/external-tables))
- **Immutable, native landing + audit columns.** `raw` mirrors the sources 1:1 with no transformation;
  only two audit columns are added - `_ingested_at`, `_source_file`.
  ([Databricks](https://www.databricks.com/blog/data-pipeline-best-practices),
  [Microsoft CAF](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/scenarios/cloud-scale-analytics/best-practices/data-lake-zones))
- **Idempotent load.** `WRITE_TRUNCATE` recreates each table atomically, so a rerun or a retry after a
  failure yields the same result - no duplicates.
  ([BigQuery: batch loading](https://docs.cloud.google.com/bigquery/docs/batch-loading-data))
- **Config in a committed `config.toml`, with env override.** A public, documented config file holds
  the non-secret defaults (project, dataset, location, source dir, keyfile *path*), so a fresh clone
  runs with no setup; any value is overridable by an env var for CI/production. The only secret (the
  service-account JSON) stays gitignored - the repo can be open-sourced safely. (This favors
  clone-and-run reproducibility over strict env-only [12-factor](https://12factor.net/config), while
  keeping its core rule: no secrets in the repo.)
- **Sample in git, source in GCS for prod.** The small synthetic sample lives in `data/` for
  reproducibility; in production the landing zone is a GCS bucket and `load_raw.py` reads from there.

## Always runs (offline safety)
The exploration scripts read the committed local sample and need **no GCP** - they always run right
after cloning. The loader has an offline mode, `OTG_SKIP_LOAD=1`, that produces the NDJSON without
touching BigQuery - so you can verify the conversion even when the warehouse is unreachable.

## Run
See [`git_manual/MANUAL_GCP_INGESTAO.md`](../../git_manual/MANUAL_GCP_INGESTAO.md), or in short:
```bash
OTG_SKIP_LOAD=1 python ingestion/load_raw.py   # test the conversion (no BigQuery)
python ingestion/load_raw.py                    # create `raw` + load (idempotent)
```
