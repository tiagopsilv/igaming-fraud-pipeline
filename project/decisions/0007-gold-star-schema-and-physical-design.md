# ADR-0007 - Gold star schema and physical design

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `exploration/explore_star_schema.py` - the descriptive entities are small (600 players,
  50 affiliates) so they become dimensions materialized as full tables; the facts carry the date
  spans (transactions 365 days, sessions 69 days) and the `player_id` cardinality (577 / 600) that
  justify **partition by date + cluster by `player_id`**; and every fact `player_id` exists in the
  player dimension (referential integrity holds).

## Context
The Gold layer feeds the Power BI dashboard and the fraud analysis. It needs a dimensional model (a
star schema - the standard for BI on BigQuery) and a physical design that keeps BigQuery fast and cheap.

## Decision
- **Dimensions:** `dim_player` (SCD Type 1, [ADR-0003](0003-scd-type-1-dim-player.md)), `dim_affiliate`
  (attribution resolved, [ADR-0004](0004-affiliate-attribution-rule.md)), `dim_date` (generated seed).
  `transaction_type` and `device` are low-cardinality **degenerate dimensions** carried on the facts,
  not separate tables.
- **Facts:** `fct_transactions` (grain = 1 transaction, measure = `amount`), `fct_sessions`
  (grain = 1 session, `ip`/`device`), `fct_fraud_signals` (grain = 1 player, flags + risk value).
- **Physical (BigQuery):** facts **partition by `DATE(timestamp)`** (day granularity - matches the
  date-range filters) and **cluster by `player_id`** (the most-used join/filter key). Dimensions are
  tiny, so they are full tables with no partitioning.
- **Materialization:** `staging` = view · `intermediate` = table · `marts` = table; the facts are
  **incremental** - `merge` for `fct_transactions` (money → idempotent) and `insert_overwrite` for
  `fct_sessions` (high-volume events).
- **Only the Gold layer feeds the dashboard.**

## Consequences
- Partition pruning + clustering cut the bytes BigQuery scans, so queries are cheaper and faster.
- Incremental facts avoid full rebuilds; reruns stay idempotent.
- The star schema is simple for the dashboard; degenerate dimensions keep the model lean.
- Referential integrity is enforced downstream by dbt `relationships` tests.
