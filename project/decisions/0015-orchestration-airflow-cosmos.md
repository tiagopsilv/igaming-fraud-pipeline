# ADR-0015 - Orchestrate the pipeline with Airflow + Astronomer Cosmos

- **Status:** Accepted
- **Date:** 2026-07-20
- **Evidence:** the dbt project already has a full DAG of models and tests (Bronze -> Silver -> Gold,
  plus unit and data tests); the question is how Airflow should run it. Benchmarked against
  Astronomer's own reference architectures (`reference-architecture-elt-bigquery-cosmos`, `cosmos-demo`),
  which render dbt as a Cosmos task group rather than a single shell call.

## Context
Deliverable **E2** requires an Airflow DAG that orchestrates ingestion, transformation and model refresh,
with retries and a failure alert. The transformation is a dbt project; the decision is *how* Airflow
invokes dbt.

## Decision
Orchestrate with **Airflow (Astro Runtime) + Astronomer Cosmos**, one DAG:
`ingest_raw -> dbt_source_freshness -> transform (DbtTaskGroup) `.
1. **Cosmos `DbtTaskGroup`** renders each dbt model and test as its *own* Airflow task
   (`TestBehavior.AFTER_EACH`), instead of a single opaque `dbt build`. This gives per-model lineage in
   the UI, retries at model grain, and tests as first-class tasks - the observability the case rewards.
2. **dbt runs in an isolated virtualenv** (`ExecutionConfig` -> `dbt_venv`), so dbt's and Airflow's
   dependency trees never clash (the recommended Cosmos pattern).
3. **`LoadMode.AUTOMATIC`**: parse the DAG from a pre-built manifest when present (fast, no `dbt ls` at
   parse), falling back to `dbt ls` otherwise. `install_deps=False` - `dbt deps` runs once in the image.
4. **Credentials via an Airflow connection** (`gcp_bigquery`), never hardcoded; the profile is built by
   Cosmos' `GoogleCloudServiceAccountFileProfileMapping`. Failure alerts post to a Discord/Slack webhook
   (`ALERT_WEBHOOK_URL`), best-effort so alerting never breaks the scheduler.
5. **Single source of truth**: the dbt project stays at repo `dbt/`; the Astro image copies it in at
   build (`include/sync_project.sh`), so there is one project, edited and tested in one place.

## Alternatives considered
- **BashOperator `dbt build`** - one task, no per-model visibility, retries re-run everything. Rejected:
  loses the lineage/observability that is half the point of orchestrating.
- **KubernetesPodOperator per dbt run** - production-scale isolation, but heavy for this case and no
  local reproducibility. Deferred as a scale path.
- **dbt Cloud** - not the assigned stack (Airflow + dbt Core).

## Consequences
- The Airflow UI shows the whole pipeline as a graph: ingest, freshness, then every model/test.
- `schedule="@daily"` is the baseline; ADR-0008's per-source cadence (sessions near-real-time,
  transactions hourly, dimensions daily) is a refinement to split into per-cadence DAGs.
- Running end to end needs Docker (`astro dev start`); the structure and DAG are in `airflow/`.
