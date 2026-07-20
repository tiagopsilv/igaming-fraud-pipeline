# Airflow orchestration (Astro + Cosmos) - deliverable E2

The DAG that orchestrates the pipeline: **ingest -> source freshness -> dbt build (models + tests)**.
The dbt run is rendered by **Astronomer Cosmos** as a `DbtTaskGroup`, so every model and test is its
own Airflow task (per-model lineage, retries at model grain, tests visible in the UI). See
[ADR-0015](../project/decisions/0015-orchestration-airflow-cosmos.md).

## Layout
```
airflow/
├── Dockerfile              # Astro Runtime + an isolated dbt venv + pre-built manifest
├── requirements.txt        # astronomer-cosmos + Google provider (Airflow env)
├── packages.txt            # OS packages (none)
├── airflow_settings.yaml   # local connection/variable template (no secrets in git)
├── dags/
│   └── igaming_fraud_pipeline_dag.py   # the DAG (Cosmos DbtTaskGroup)
└── include/
    ├── sync_project.sh     # copies ../dbt + ../ingestion into the build context
    ├── dbt/                # build-time COPY of the repo dbt project (gitignored)
    └── ingestion/          # build-time COPY of the ingestion code (gitignored)
```

**Single source of truth:** the dbt project is edited and tested at repo-root `../dbt`. `sync_project.sh`
makes a build-time copy under `include/dbt` so the image is self-contained; the copy is gitignored.

## Run it (local)
```bash
# 0) one-time: install the Astro CLI (https://docs.astronomer.io/astro/cli/install-cli)
cd airflow
bash include/sync_project.sh                 # copy the dbt project + ingestion into the image
mkdir -p include/secrets                     # drop your gcp-keyfile.json here (gitignored)
cp ../secrets/gcp-keyfile.json include/secrets/ 2>/dev/null || true
astro dev start                              # builds the image and starts Airflow at localhost:8080
```
Open http://localhost:8080 (admin/admin), enable `igaming_fraud_pipeline`, trigger a run.

## Credentials & alerts (no secrets in git)
- **BigQuery**: the `gcp_bigquery` Airflow connection (see `airflow_settings.yaml`) points at a
  service-account JSON mounted from `include/secrets/` (gitignored). The DAG hardcodes nothing.
- **Failure alerts**: set the Airflow Variable `ALERT_WEBHOOK_URL` to a Discord/Slack webhook to get a
  message on any task failure; unset = alerts silently skipped.

## Notes
- `schedule="@daily"` is the baseline. ADR-0008 defines a per-source cadence (sessions near-real-time,
  transactions hourly, dimensions daily) - the production refinement is to split into per-cadence DAGs.
- `install_deps=False`: `dbt deps` runs once in the image, not per task (the recommended Cosmos setting).
