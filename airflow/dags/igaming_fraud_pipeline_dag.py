"""
igaming_fraud_pipeline - the orchestration DAG (deliverable E2).

Flow: ingest raw -> source freshness -> dbt build (models + tests) -> done.
The dbt run is rendered by Astronomer Cosmos as a DbtTaskGroup, so every model and test
is its OWN Airflow task - real per-model lineage, retries at model grain, and tests visible
in the UI (not a single opaque `dbt build`). See ADR-0015.

Nothing secret lives here: BigQuery credentials come from the Airflow connection `gcp_bigquery`
(for the dbt run) and from a mounted keyfile path passed via env (for the ingestion/freshness steps).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib import request as _urlrequest

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator

from cosmos import (
    DbtTaskGroup,
    ExecutionConfig,
    ProfileConfig,
    ProjectConfig,
    RenderConfig,
)
from cosmos.constants import LoadMode, TestBehavior          # safe, stable location for the enums
from cosmos.profiles import GoogleCloudServiceAccountFileProfileMapping

# --- paths inside the container (the project is copied into include/ at build time) ----------
AIRFLOW_HOME = Path(os.environ.get("AIRFLOW_HOME", "/usr/local/airflow"))
DBT_PROJECT_PATH = AIRFLOW_HOME / "include" / "dbt"
DBT_EXECUTABLE = AIRFLOW_HOME / "dbt_venv" / "bin" / "dbt"
VENV_PYTHON = AIRFLOW_HOME / "dbt_venv" / "bin" / "python"
INGESTION_SCRIPT = AIRFLOW_HOME / "include" / "ingestion" / "load_raw.py"
GCP_KEYFILE = (AIRFLOW_HOME / "include" / "secrets" / "gcp-keyfile.json").as_posix()

# Credentials for the two BashOperator steps (ingest, freshness). The dbt profile and the
# ingestion both read these env names (same as config.toml); the keyfile stays gitignored.
# append_env=True on the operators keeps PATH etc. - setting env alone would wipe the shell env.
DBT_ENV = {
    "OTG_GCP_KEYFILE": GCP_KEYFILE,
    "GOOGLE_APPLICATION_CREDENTIALS": GCP_KEYFILE,
    "OTG_GCP_PROJECT": os.environ.get("OTG_GCP_PROJECT", "otg-igaming-case"),
    "OTG_BQ_LOCATION": os.environ.get("OTG_BQ_LOCATION", "US"),
    "OTG_DBT_DATASET": os.environ.get("OTG_DBT_DATASET", "analytics"),
}

# =============================================================================================
# Passo 2 - connect dbt to BigQuery WITHOUT a secret in code: the profile is built from the
# Airflow connection `gcp_bigquery` (Cosmos writes the profiles.yml at runtime).
# =============================================================================================
profile_config = ProfileConfig(
    profile_name="igaming",
    target_name="prod",
    profile_mapping=GoogleCloudServiceAccountFileProfileMapping(
        conn_id="gcp_bigquery",
        profile_args={
            "project": DBT_ENV["OTG_GCP_PROJECT"],
            "dataset": DBT_ENV["OTG_DBT_DATASET"],
            "location": DBT_ENV["OTG_BQ_LOCATION"],
            "threads": 4,
        },
    ),
)

# =============================================================================================
# Passo 3 - point Cosmos at the project, the dbt to run, and how to discover the models.
#   ProjectConfig    = where the dbt project is
#   ExecutionConfig  = which dbt runs it (the isolated venv, LOCAL execution mode by default)
#   RenderConfig     = how the DAG is parsed (AUTOMATIC = manifest if present, else `dbt ls`);
#                      TestBehavior.AFTER_EACH runs a model's tests right after that model.
# =============================================================================================
project_config = ProjectConfig(dbt_project_path=DBT_PROJECT_PATH.as_posix())
execution_config = ExecutionConfig(dbt_executable_path=DBT_EXECUTABLE.as_posix())
render_config = RenderConfig(
    load_method=LoadMode.AUTOMATIC,
    test_behavior=TestBehavior.AFTER_EACH,
)


# =============================================================================================
# Passo 6 - failure alert (provider-agnostic: works with a Discord or Slack webhook).
# =============================================================================================
def notify_webhook(context) -> None:
    """Post a short failure message to ALERT_WEBHOOK_URL. Never raises - alerting must not
    break the scheduler. The URL comes from an Airflow Variable or env var; if unset, skip."""
    url = Variable.get("ALERT_WEBHOOK_URL", default_var=os.environ.get("ALERT_WEBHOOK_URL", ""))
    if not url:
        return
    ti = context.get("task_instance")
    text = f":rotating_light: iGaming pipeline FAILED - task `{ti.task_id}` (dag `{ti.dag_id}`, run {context.get('run_id')})"
    try:
        payload = f'{{"content": "{text}", "text": "{text}"}}'.encode("utf-8")
        req = _urlrequest.Request(url, data=payload, headers={"Content-Type": "application/json"})
        _urlrequest.urlopen(req, timeout=10)  # noqa: S310 (trusted, operator-configured URL)
    except Exception:  # noqa: BLE001 - alerting is best-effort
        pass


default_args = {
    "owner": "data-engineering",
    "retries": 2,                          # ride out a transient failure (network, quota)
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_webhook,  # a real failure pings the webhook
}

with DAG(
    dag_id="igaming_fraud_pipeline",
    description="Ingest four sources, transform through Medallion (dbt), surface fraud signals.",
    schedule="@daily",          # daily baseline; see ADR-0008 for the per-source cadence refinement
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["igaming", "dbt", "fraud", "medallion"],
) as dag:

    # ingest -> freshness -> transform, in that order (preceded by a one-off dbt deps).

    # 0) dbt deps: install the dbt packages INTO the mounted project at runtime. The image installs
    #    them at build, but the local bind-mount hides that copy, and a fresh clone has no dbt_packages
    #    (it is gitignored). This task makes the DAG self-sufficient - no pre-sync of packages needed,
    #    so it runs on a clean clone. `dbt deps` needs no warehouse credentials.
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=(
            f"cd {DBT_PROJECT_PATH.as_posix()} && {DBT_EXECUTABLE.as_posix()} deps"
        ),
    )

    # 1) Ingest: land the four sources into the `raw` dataset (idempotent, ADR-0005). Writing a
    #    fresh _ingested_at here is what makes the freshness check below pass on the static sample.
    ingest_raw = BashOperator(
        task_id="ingest_raw",
        bash_command=f"{VENV_PYTHON.as_posix()} {INGESTION_SCRIPT.as_posix()}",
        env=DBT_ENV,
        append_env=True,
    )

    # 2) Source freshness: fail fast if the just-landed data is stale (observability point, R1).
    source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=(
            f"cd {DBT_PROJECT_PATH.as_posix()} && "
            f"{DBT_EXECUTABLE.as_posix()} source freshness --profiles-dir {DBT_PROJECT_PATH.as_posix()}"
        ),
        env=DBT_ENV,
        append_env=True,
    )

    # =========================================================================================
    # Passo 4 - the heart: Cosmos renders every Bronze/Silver/Gold model and its tests as tasks.
    # =========================================================================================
    transform = DbtTaskGroup(
        group_id="transform",
        project_config=project_config,
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=render_config,
        operator_args={"install_deps": False},  # deps are baked into the image, not per task
    )

    dbt_deps >> ingest_raw >> source_freshness >> transform
