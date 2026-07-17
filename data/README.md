# data/ - sample source data (for reproducibility)

These four files are the **synthetic sample** the pipeline ingests. They are committed here for one
reason: **reproducibility** - anyone can clone the repo and run the exploration and ingestion without
extra setup ("runs on first try").

- `players.json`, `sessions.json` - pretty-printed JSON arrays (must be converted to NDJSON on load).
- `transactions.csv`, `affiliate_cpa_ftd.csv` - CSV.
- `gerar_datasets_case.py` - the generator, included to make explicit that the data is **synthetic and
  random** (no planted fraud).

## This is a sample, not a landing zone
In production the raw data does **not** live in git. A landing zone is **immutable object storage**
(e.g. a GCS bucket): raw events land there in their native format, untouched, before any transform
([Databricks](https://www.databricks.com/blog/data-pipeline-best-practices),
[Microsoft CAF](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/scenarios/cloud-scale-analytics/best-practices/data-lake-zones)).
Git holds **code + a small sample**; the real source location is configurable (see `ingestion/`).

> Note: these are **source data**, not reference data - so they are **not** dbt seeds. Seeds are for
> small, static lookups (country→currency, thresholds), and dbt explicitly says seeds must not be used
> for raw/source data.
