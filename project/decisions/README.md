# Architecture Decision Records (ADRs)

Each ADR captures **one significant decision**: its context, the option chosen, the alternatives
considered, and the consequences. They follow a lightweight
[MADR](https://adr.github.io/madr/)-style format and are kept short (about one page).

**Rules**
- **Every ADR is evidence-based.** Each one cites, in an `Evidence:` field, the
  `exploration/*.py` script whose output demonstrates the conclusion. Decisions come from exploring
  the data, not from opinion - the exploration scripts are written as an architect *discovering* the
  data step by step.
- ADRs are an immutable timeline. Do not rewrite a decided ADR - if a decision changes, add a new
  ADR that supersedes the old one and mark the old one `Superseded by ADR-XXXX`.
- Create an ADR only when a decision affects architecture, data modeling, operations, or long-term
  maintenance - not for trivial choices.

**Status values:** `Proposed` · `Accepted` · `Superseded`

## Index
| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-medallion-architecture.md) | Medallion architecture (Bronze / Silver / Gold) | Accepted |
| [0002](0002-resolve-affiliate-attribution-in-silver.md) | Resolve affiliate attribution in the Silver layer | Accepted |
| [0003](0003-scd-type-1-dim-player.md) | SCD Type 1 for `dim_player` | Accepted |
| [0004](0004-affiliate-attribution-rule.md) | Affiliate attribution rule (claim-FTD gated on real deposit) | Accepted |
| [0005](0005-raw-ingestion-idempotent-ndjson.md) | Raw ingestion: idempotent NDJSON load into a `raw` dataset | Accepted |
| [0006](0006-data-contract-and-assumptions.md) | Data contract and core assumptions (grain, UTC, account, fraud) | Accepted |
| [0007](0007-gold-star-schema-and-physical-design.md) | Gold star schema and physical design (partition/cluster/materialization) | Accepted |
| [0008](0008-load-strategy-per-source.md) | Load strategy per source (frequency, full/incremental, control field) | Accepted |
| [0009](0009-non-functional-requirements.md) | Non-functional requirements (freshness, quality, cost, reliability SLOs) | Accepted |
| [0010](0010-bronze-staging-conventions.md) | Bronze staging conventions (SAFE_CAST, per-source parse, sources + tests, boundary) | Accepted |
| [0011](0011-attribution-gates-on-qualified-ftd.md) | Attribution gates on the qualified FTD (deposit + bet baseline) | Accepted |
| [0012](0012-silver-intermediate-conventions.md) | Silver intermediate conventions and the wallet ledger | Accepted |
| [0013](0013-gold-fraud-signals-risk-score.md) | Gold fraud signals and the multi-signal risk score (R2) | Accepted |
| [0014](0014-gold-serving-model-for-power-bi.md) | Gold serving model for Power BI (star schema, Import mode) | Accepted |
| [0015](0015-orchestration-airflow-cosmos.md) | Orchestrate the pipeline with Airflow + Astronomer Cosmos | Accepted |
