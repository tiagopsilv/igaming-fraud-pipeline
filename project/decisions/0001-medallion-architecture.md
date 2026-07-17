# ADR-0001 - Medallion architecture (Bronze / Silver / Gold)

- **Status:** Accepted
- **Date:** 2026-07-16
- **Evidence:** `exploration/explore_sources.py` - four heterogeneous sources (JSON arrays vs CSV,
  three date formats, `amount` as text, a conflated affiliate grain) that must be conformed and typed
  before analytics, which is what motivates layered separation.

## Context
The pipeline ingests four heterogeneous sources (JSON and CSV) that must be cleaned, conformed, and
served for analytics and fraud detection. We need clear layer boundaries, per-layer data-quality
gates, and a BI tool that is decoupled from raw ingestion details.

## Decision
Adopt the Medallion architecture, mapped onto dbt's standard layout:
- **Bronze** = `models/staging/` - one `stg_` model per source, 1:1 with the raw data, no business
  rules (rename to snake_case, cast types per source, normalize money to NUMERIC). Materialized as **views**.
- **Silver** = `models/intermediate/` - conform, join, and apply business rules (email
  normalization, derive the real first deposit, resolve affiliate attribution, data-quality validation).
- **Gold** = `models/marts/` - a star schema of dimensions and facts plus `fct_fraud_signals`.
- **BI reads only the Gold layer.** A model may reference only its own layer or the one below.

## Consequences
- Clear ownership and testability at each stage; business rules live in one place (Silver).
- BI is insulated from changes in the source formats.
- More models to maintain than a flat approach - an acceptable trade for clarity and testing.
