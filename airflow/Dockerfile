# Astro Runtime = Airflow + sane production defaults. Pin the version for reproducibility.
FROM quay.io/astronomer/astro-runtime:12.7.1

# dbt lives in its OWN virtualenv, isolated from Airflow's Python, so their dependency trees
# never clash (the recommended Cosmos pattern). Cosmos calls this dbt via ExecutionConfig.
# Pinned to the 1.11 line (the version the project was built and tested with): dbt 1.12 makes the
# `--models` flag a FATAL error, and Cosmos 1.8.x still emits `--models`, so 1.12 breaks the run.
RUN python -m venv dbt_venv && \
    . dbt_venv/bin/activate && \
    pip install --no-cache-dir "dbt-core>=1.11,<1.12" "dbt-bigquery>=1.11,<1.12" && \
    deactivate

# Pre-build the dbt manifest so Cosmos parses the DAG from it (fast, no `dbt ls` at parse time).
# `dbt deps` + `dbt parse` need no live warehouse; if the profile can't resolve at build, Cosmos
# falls back to LoadMode.AUTOMATIC's `dbt ls` at runtime - so this is best-effort (|| true).
ENV DBT_PROFILES_DIR=/usr/local/airflow/include/dbt
RUN . dbt_venv/bin/activate && \
    cd include/dbt && \
    dbt deps && dbt parse || true
