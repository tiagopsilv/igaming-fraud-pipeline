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

## 🔵 Phase 2 - Modeling (now)
Build the Medallion models against the decisions above.
- ✅ Data contract locked ([ADR-0006](decisions/0006-data-contract-and-assumptions.md)): grain per
  table, UTC timezone, and "account" = `player_id` (fraud signals are designed later, in the Gold layer).
- ✅ Gold star schema & physical design ([ADR-0007](decisions/0007-gold-star-schema-and-physical-design.md)):
  dimensions, facts, partition-by-date + cluster-by-`player_id`, and materialization per layer.
- ✅ **E4 - load-strategy table** ([ADR-0008](decisions/0008-load-strategy-per-source.md)): per source,
  frequency × full/incremental × control field × rationale.
- ✅ **Non-functional requirements** ([ADR-0009](decisions/0009-non-functional-requirements.md)):
  freshness / quality / cost / reliability SLOs, derived from a measured baseline.
- ✅ **E1 - architecture diagram** (`docs/architecture.md`, C4 / data-flow) and the
  **source-to-target mapping** (`docs/source_to_target_mapping.md`).

The architecture is now fully specified (contract, star schema, load strategy, NFRs, diagram, STTM).
The build then runs layer by layer, each with its conventions locked first.
- ✅ **Bronze staging conventions** ([ADR-0010](decisions/0010-bronze-staging-conventions.md)):
  `SAFE_CAST` on every typed column (autodetect had mistyped `amount` as FLOAT), sources + freshness,
  and the structural test suite (unique/not_null, accepted_values, non-negative, no-future, not-null-after-cast).
- 🔵 **E3 - dbt models** (in progress):
  - ✅ **Bronze staging** (`dbt/models/staging/`): the four `stg_` models (`SAFE_CAST` on every typed
    column, fixing `amount` that autodetect typed FLOAT to NUMERIC; view materialization) with their test
    suite (unique/not_null, accepted_values, non-negative, no-future, not-null-after-cast) plus source
    freshness. Built test-first and passing against BigQuery (`dbt build`, 39 checks green). ADR-0010.
  - **Silver** (conform, real FTD, attribution, data-quality) → **Gold** star schema.
- **R2 - Fraud signals** in `fct_fraud_signals`: multi-accounting, AML low-play, affiliate ghost-FTD.

## ⬜ Phase 3 - Orchestrate, serve & harden
- **E2 - Airflow DAG** (Cosmos): ingest → dbt build → publish.
- **R1 - Observability**: source freshness, row-count/volume, schema drift, anomaly monitors.
- **E5 - Power BI dashboard**: Fraud Overview / Affiliate Metrics / Financial Signals.
- CI (GitHub Actions: `pytest` + `ruff` + `dbt build`), quickstart docs, end-to-end clean-environment run.

---

## Fraud, risk & quality grow with the pipeline
Findings emerge progressively; each layer is a chance to surface new risk and fraud as it is built.
The method is consistent throughout:
1. **Explore** the layer (a detective pass over what it must handle).
2. **Record** any decision it settles as an evidence-based **ADR**.
3. **Enforce** the findings where they belong: recurring assertions become **dbt tests**, ongoing
   profiling becomes **observability**, and format handling lives in **ingestion / Bronze**.

Non-exploration code is developed **test-first (TDD)** with `pytest` + `ruff`; dbt models are covered
by dbt tests. Everything is green before it ships.
