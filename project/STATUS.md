# Project Status

**Project:** iGaming fraud-detection data pipeline - Medallion architecture (BigQuery + dbt + Airflow) feeding a Power BI dashboard.
**Goal:** ingest four heterogeneous sources (JSON/CSV), model them in Bronze/Silver/Gold, and surface fraud signals plus affiliate and financial metrics.
**Status:** ✅ Complete - all deliverables built: the architecture, the Airflow DAG (validated end-to-end), the full **Bronze + Silver + Gold** dbt layers (star schema, fraud signals, contracts, exposure), the load-strategy table, and the Power BI dashboard, plus observability and the fraud-signal layer.
**Last updated:** 2026-07-20

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
cd dbt && dbt deps && dbt build --profiles-dir .   # Bronze + Silver + Gold models + tests
```

## Deliverables & progress
| Deliverable | Status |
|-------------|--------|
| Architecture diagram | ✅ done (`docs/architecture.md`) |
| Airflow DAG (ingest → transform → refresh) | ✅ built + **validated running** (`astro dev start`): 38 tasks green end-to-end, retries + alert confirmed (ADR-0015) |
| dbt models - Bronze / Silver / Gold | ✅ done (all three layers built + tested) |
| Load-strategy table | ✅ done (ADR-0008) |
| Power BI dashboard (Fraud / Acquisition / Affiliate / Financial) | ✅ done (`dashboard/igaming_fraud_dashboard.pbix`: four pages over the Gold marts; design in `docs/dashboard.md`) |
| Observability points | ✅ instrumented (Elementary: run/test logging + schema-drift + volume anomaly monitors, ADR-0016) |
| ≥ 2 fraud signals in the Gold layer | ✅ done (`fct_fraud_signals`: 5 core + 5 secondary) |

Legend: ✅ done · 🟡 in progress · ⬜ next

## Delivered so far
- Cloud foundation: BigQuery project, least-privilege service account, dbt connected.
- Data discovery across the four sources (`exploration/`).
- Architecture decided as evidence-based ADRs.
- Ingestion layer: NDJSON normalization + audit columns + idempotent load into `raw`, unit-tested.
- Bronze staging (`dbt/`): four `stg_` models (SAFE_CAST on every typed column, fixing `amount` that
  autodetect typed FLOAT to NUMERIC) with their test suite (unique/not_null, accepted_values,
  non-negative, no-future, not-null-after-cast) and source freshness. Passing on BigQuery (`dbt build`).
- Silver intermediate (`dbt/`): seven `int_` models (conformed player, real + qualified FTD, affiliate
  attribution, per-player financials, activity, and the wallet **ledger** with running balance).
  Structural tests pass; the business-rule DQ tests surface the sample's inconsistencies as warnings.
- Gold marts (`dbt/models/marts/`): the star schema - `dim_player` (SCD-1), `dim_affiliate`, `dim_date`,
  `fct_transactions` (incremental **merge**, carries the ledger balance), `fct_sessions` (incremental
  **insert_overwrite**), **`fct_fraud_signals`** (5 core signals + risk score + 5 secondary flags) and
  `agg_affiliate_performance` (CPA / ROI / ghost-FTD). Every mart has an **enforced model contract**;
  a **dbt exposure** ties them to the Power BI dashboard for end-to-end lineage. `dbt build` green,
  incremental idempotency proven on a second run (ADR-0007/0013/0014).
- Test suite: **dbt unit tests** validate the business logic (qualified-FTD baseline, attribution,
  Net Deposit, ledger balance, the fraud risk score, affiliate ROI) on static fixtures; **business-rule
  consistency tests** confirm the modeled layers hold on the real data (ledger reconciles, risk score
  matches its flags, no player dropped, CPA only for qualified). Full `dbt build`: **125 pass, 0 error**
  (4 warnings are the intended Silver `severity: warn` checks on the raw sample).

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
[0010 Bronze staging conventions](decisions/0010-bronze-staging-conventions.md) ·
[0011 attribution gates on qualified FTD](decisions/0011-attribution-gates-on-qualified-ftd.md) ·
[0012 Silver intermediate conventions & the ledger](decisions/0012-silver-intermediate-conventions.md) ·
[0013 Gold fraud signals & risk score](decisions/0013-gold-fraud-signals-risk-score.md) ·
[0014 Gold serving model for Power BI](decisions/0014-gold-serving-model-for-power-bi.md) ·
[0015 orchestration with Airflow + Cosmos](decisions/0015-orchestration-airflow-cosmos.md)
