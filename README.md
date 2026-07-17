# iGaming Fraud-Detection Data Pipeline

A data pipeline that ingests four heterogeneous sources (JSON/CSV), models them through a
**Medallion architecture** (Bronze → Silver → Gold) on **BigQuery** with **dbt**, orchestrated by
**Airflow**, and serves fraud signals plus affiliate and financial metrics to a **Power BI** dashboard.

**Status:** 🟡 In progress - foundation, data discovery, architecture and the ingestion layer are
delivered; the Medallion models are being built next. The phased plan is in **[project/ROADMAP.md](project/ROADMAP.md)**.

## The problem
An operator receives data on user acquisition (affiliates), player behavior (sessions), and money
movements (transactions). The pipeline ingests and structures it so analysts can detect fraud and
measure affiliate and financial performance.

## Stack
Airflow (Astronomer Cosmos) · dbt · Google BigQuery · Power BI · Python. Local dev on Docker / Astro CLI.

## Repository layout
```
data/            # synthetic source sample (for reproducibility; production lands in GCS)
config.toml      # public pipeline configuration (env-overridable; no secrets)
ingestion/       # land the sources into BigQuery - NDJSON + audit columns + idempotent load
dbt/             # dbt project: Bronze staging models + tests (Silver/Gold next)
exploration/     # one-time discovery scripts (profiling + architecture analysis)
docs/            # architecture diagram (E1) + source-to-target mapping (STTM)
tests/           # unit tests (pytest)
project/         # ROADMAP · STATUS · CHANGELOG · decisions (ADRs)
requirements*.txt
```

## Quickstart
Requires **Python 3.11+** (the loader reads config via the stdlib `tomllib`).
```bash
pip install -r requirements-dev.txt
python exploration/explore_sources.py    # get to know the data (offline)
python ingestion/load_raw.py             # land the sources into BigQuery - see git_manual note
pytest tests/ -q                         # run the tests
```
Configure your own project in `config.toml` and drop a service-account key at the path it names.

## How decisions are made
Every architecture decision is an **evidence-based ADR** ([project/decisions/](project/decisions/)):
each one cites the exploration script that demonstrates it. New risk and fraud findings surface as
each layer is built, and are enforced where they belong - as dbt tests, observability, or ingestion
handling.

## A note on the data
Analysis established that the four sample datasets are **synthetic and random** (zero nulls, inverted
money flow, impossible sequences such as withdrawals without deposits). The fraud signals are
therefore built as **production-grade logic**, validated against the data - the honest, analytical
framing this case calls for.

## Planning & decisions
[Roadmap](project/ROADMAP.md) · [Status](project/STATUS.md) · [Changelog](project/CHANGELOG.md) ·
[Decisions (ADRs)](project/decisions/)
