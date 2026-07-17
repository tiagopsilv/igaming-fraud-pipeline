# Project Status

**Project:** iGaming fraud-detection data pipeline - Medallion architecture (BigQuery + dbt + Airflow) feeding a Power BI dashboard.
**Goal:** ingest four heterogeneous sources (JSON/CSV), model them in Bronze/Silver/Gold, and surface fraud signals plus affiliate and financial metrics.
**Status:** 🟡 In progress - foundation, discovery, architecture and ingestion delivered; modeling the Medallion layers now.
**Last updated:** 2026-07-17

> Single source of truth for progress:
> - **`ROADMAP.md`** - the phased plan.
> - **`STATUS.md`** (this file) - snapshot of where things stand.
> - **`CHANGELOG.md`** - dated milestones and findings.
> - **`decisions/`** - Architecture Decision Records (ADRs).

## Stack
Airflow (Astronomer Cosmos) · dbt · Google BigQuery · Power BI · Python. Local dev on Docker / Astro CLI.

## How to run
```bash
python exploration/explore_sources.py    # data discovery (offline)
python ingestion/load_raw.py             # land the sources into BigQuery (git_manual/MANUAL_GCP_INGESTAO.md)
pytest tests/ -q                         # unit tests
cd dbt && dbt deps && dbt build --profiles-dir . --select staging   # Bronze models + tests (git_manual/MANUAL_DBT_BRONZE.md)
```

## Deliverables & progress
| ID | Deliverable | Status |
|----|-------------|--------|
| E1 | Architecture diagram | ✅ done (`docs/architecture.md`) |
| E2 | Airflow DAG (ingest → transform → refresh) | ⬜ next |
| E3 | dbt models - Bronze / Silver / Gold | 🟡 in progress (Bronze staging done) |
| E4 | Load-strategy table | ✅ done (ADR-0008) |
| E5 | Power BI dashboard (Fraud / Affiliate / Financial) | ⬜ next |
| R1 | Observability points | ⬜ next |
| R2 | ≥ 2 fraud signals in the Gold layer | 🟡 designed |

Legend: ✅ done · 🟡 in progress · ⬜ next

## Delivered so far
- Cloud foundation: BigQuery project, least-privilege service account, dbt connected.
- Data discovery across the four sources (`exploration/`).
- Architecture decided as evidence-based ADRs.
- Ingestion layer: NDJSON normalization + audit columns + idempotent load into `raw`, unit-tested.
- Bronze staging (`dbt/`): four `stg_` models (SAFE_CAST on every typed column, fixing `amount` that
  autodetect typed FLOAT to NUMERIC) with their test suite (unique/not_null, accepted_values,
  non-negative, no-future, not-null-after-cast) and source freshness. Passing on BigQuery (`dbt build`).

## Key decisions
[ADR-0001 Medallion](decisions/0001-medallion-architecture.md) ·
[0002 attribution in Silver](decisions/0002-resolve-affiliate-attribution-in-silver.md) ·
[0003 SCD-1 dim_player](decisions/0003-scd-type-1-dim-player.md) ·
[0004 attribution rule](decisions/0004-affiliate-attribution-rule.md) ·
[0005 idempotent NDJSON ingestion](decisions/0005-raw-ingestion-idempotent-ndjson.md) ·
[0006 data contract & assumptions](decisions/0006-data-contract-and-assumptions.md) ·
[0007 Gold star schema & physical design](decisions/0007-gold-star-schema-and-physical-design.md) ·
[0008 load strategy per source](decisions/0008-load-strategy-per-source.md) ·
[0009 non-functional requirements](decisions/0009-non-functional-requirements.md) ·
[0010 Bronze staging conventions](decisions/0010-bronze-staging-conventions.md)
