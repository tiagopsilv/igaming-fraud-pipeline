# Roadmap

**Mission:** deliver an iGaming fraud-detection data pipeline. Four heterogeneous sources ingested
and modeled through a Medallion architecture (BigQuery + dbt + Airflow) and served as a Power BI
dashboard that surfaces fraud signals and affiliate / financial metrics.

The plan runs in phases, **architect → engineer**: the architecture is decided first (layers, grain,
load strategy) and recorded as [ADRs](decisions/); the pipeline is then built against those decisions.
Each phase also **deepens the fraud, risk and data-quality analysis** as more of the pipeline exists.

---

## ✅ Phase 0 - Foundation & discovery
- Cloud + tooling foundation: BigQuery project, least-privilege service account, dbt connected.
- Data discovery across all four sources (`exploration/`): profiling, quality findings, grain analysis.
- Architecture decided and recorded as evidence-based ADRs:
  [0001](decisions/0001-medallion-architecture.md) · [0002](decisions/0002-resolve-affiliate-attribution-in-silver.md) ·
  [0003](decisions/0003-scd-type-1-dim-player.md) · [0004](decisions/0004-affiliate-attribution-rule.md).

## ✅ Phase 1 - Ingestion
- Land the four sources into the BigQuery `raw` dataset: NDJSON normalization with audit columns and
  an idempotent `WRITE_TRUNCATE` load, config-driven and offline-testable, developed test-first.
  See [ADR-0005](decisions/0005-raw-ingestion-idempotent-ndjson.md).
- **Discovery:** the ingestion-readiness pass caught that the sources are CRLF (the loader writes LF).

## ✅ Phase 2 - Modeling
Build the Medallion models against the decisions above.
- ✅ Data contract locked ([ADR-0006](decisions/0006-data-contract-and-assumptions.md)): grain per
  table, UTC timezone, and "account" = `player_id` (fraud signals are designed later, in the Gold layer).
- ✅ Gold star schema & physical design ([ADR-0007](decisions/0007-gold-star-schema-and-physical-design.md)):
  dimensions, facts, partition-by-date + cluster-by-`player_id`, and materialization per layer.
- ✅ **Load-strategy table** ([ADR-0008](decisions/0008-load-strategy-per-source.md)): per source,
  frequency × full/incremental × control field × rationale.
- ✅ **Non-functional requirements** ([ADR-0009](decisions/0009-non-functional-requirements.md)):
  freshness / quality / cost / reliability SLOs, derived from a measured baseline.
- ✅ **Architecture diagram** (`docs/architecture.md`, C4 / data-flow) and the
  **source-to-target mapping** (`docs/source_to_target_mapping.md`).

The architecture is now fully specified (contract, star schema, load strategy, NFRs, diagram, STTM).
The build then runs layer by layer, each with its conventions locked first.
- ✅ **Bronze staging conventions** ([ADR-0010](decisions/0010-bronze-staging-conventions.md)):
  `SAFE_CAST` on every typed column (autodetect had mistyped `amount` as FLOAT), sources + freshness,
  and the structural test suite (unique/not_null, accepted_values, non-negative, no-future, not-null-after-cast).
- ✅ **dbt models**:
  - ✅ **Bronze staging** (`dbt/models/staging/`): the four `stg_` models (`SAFE_CAST` on every typed
    column, fixing `amount` that autodetect typed FLOAT to NUMERIC; view materialization) with their test
    suite (unique/not_null, accepted_values, non-negative, no-future, not-null-after-cast) plus source
    freshness. Built test-first and passing against BigQuery (`dbt build`, 39 checks green). ADR-0010.
  - ✅ **Silver intermediate** (`dbt/models/intermediate/`): seven `int_` models (conformed player,
    real + qualified FTD [ADR-0011], affiliate attribution, per-player financials, activity, and the
    **wallet ledger** with a running balance). Structural tests pass; the business-rule data-quality
    tests (funnel logic, no transaction before signup, ledger integrity) surface the sample's
    inconsistencies as warnings. Built test-first, passing against BigQuery (`dbt build`).
  - ✅ **Gold marts** (`dbt/models/marts/`): the star schema - `dim_player` (SCD-1), `dim_affiliate`,
    `dim_date`, `fct_transactions` (incremental **merge**, carries the ledger running balance),
    `fct_sessions` (incremental **insert_overwrite**), **`fct_fraud_signals`** and
    `agg_affiliate_performance`. Every mart has an **enforced contract**; a **dbt exposure** links them
    to the Power BI dashboard. `dbt build` green; incremental idempotency proven. ADR-0007/0013/0014.
- ✅ **Fraud signals** in `fct_fraud_signals`: five core (affiliate ghost-FTD, AML low-play, IP
  velocity, ledger anomaly, net-negative) combined into a **risk score**, plus five secondary flags,
  each with a value at risk. [ADR-0013](decisions/0013-gold-fraud-signals-risk-score.md).

## ✅ Phase 3 - Orchestrate, serve & harden
- ✅ **Airflow DAG** (Cosmos): the `airflow/` Astro project and the DAG
  (`ingest_raw → dbt_source_freshness → transform` as a **`DbtTaskGroup`**), with retries, a webhook
  failure alert and no secrets in code. **Validated running** via `astro dev start`: all 38 tasks green
  end-to-end (ingest → freshness → 36 dbt run/test), 0 failures.
  [ADR-0015](decisions/0015-orchestration-airflow-cosmos.md).
- ✅ **Observability**: instrumented with **Elementary** (run/test logging + `schema_changes` drift
  monitor on the sources + `volume_anomalies` on the high-volume events), on top of source freshness.
  [ADR-0016](decisions/0016-observability-with-elementary.md).
- ✅ **Power BI dashboard**: `dashboard/igaming_fraud_dashboard.pbix` - four pages (Fraud Overview /
  Acquisition & Retention / Affiliate Metrics / Financial Signals) over the Gold marts (Import mode,
  ADR-0014). The design, layout and reasoning are in [docs/dashboard.md](../docs/dashboard.md).
- ⬜ Optional next: CI (GitHub Actions: `pytest` + `ruff` + `dbt build`), quickstart docs, clean-environment run.

---

## Fraud, risk & quality grow with the pipeline
Findings emerge progressively; each layer is a chance to surface new risk and fraud as it is built.
The method is consistent throughout:
1. **Explore** the layer (an investigative pass over what it must handle).
2. **Record** any decision it settles as an evidence-based **ADR**.
3. **Enforce** the findings where they belong: recurring assertions become **dbt tests**, ongoing
   profiling becomes **observability**, and format handling lives in **ingestion / Bronze**.

Non-exploration code is developed **test-first (TDD)** with `pytest` + `ruff`; dbt models are covered
by dbt tests. Everything is green before it ships.
