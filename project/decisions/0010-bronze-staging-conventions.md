# ADR-0010 - Bronze staging conventions

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `exploration/explore_staging.py` - Q1 **queries the real raw schema in BigQuery** and
  finds that autodetect **typed the columns** from their string content (timestamps -> TIMESTAMP,
  `created_at` -> DATE, counts -> INTEGER) and, critically, typed **`amount` as FLOAT** - a money column,
  which must never be FLOAT. Q2 derives the cast contract that fixes this; Q4 shows `SAFE_CAST` never
  crashes on a bad value; Q5 measures the structural baseline (0 non-positive amounts, 0 negative counts,
  0 future timestamps, 0 duplicate primary keys, 0 nulls) and the category lists for
  `transaction_type` / `device` / `country`.

## Context
Bronze is the dbt **staging** layer ([ADR-0001](0001-medallion-architecture.md)): one `stg_` model per
source, 1:1 with the raw table, materialized as a **view**. Before writing the four models, the
conventions must be fixed so the layer is uniform, testable, and its boundary with Silver is explicit.
Market consensus is that staging does only renaming, type casting, and light structural cleanup - no
joins, no aggregations, no business logic.

## Decision - the conventions
1. **One `stg_` per source, 1:1, view.** CTE pattern `source -> renamed/cast`. Naming: `stg_<source>`.
2. **`SAFE_CAST` every typed column** (do not trust autodetect): `amount` and `cpa_value` -> **NUMERIC**
   (autodetect typed `amount` FLOAT and `cpa_value` INTEGER - money must be NUMERIC), `clicks`/
   `registrations`/`ftd` -> **INT64**, `created_at` -> **DATE**, event timestamps -> **TIMESTAMP** (UTC).
   `SAFE_CAST(x AS TIMESTAMP)` is robust whether autodetect gave TIMESTAMP (a no-op) or a STRING (it
   parses), and `SAFE_CAST` turns any bad value into NULL-and-flagged instead of failing the whole load.
3. **Rename** to target names: `type` -> `transaction_type`, `timestamp` -> `txn_ts` / `session_ts`;
   everything else is already snake_case. The audit columns (`_ingested_at`, `_source_file`) pass through.
4. **Declare the raw as dbt sources** in `_sources.yml` with `loaded_at_field = _ingested_at` and
   freshness thresholds from [ADR-0009](0009-non-functional-requirements.md); add **source-level**
   `unique`/`not_null` tests so an ingestion failure is caught before staging runs.
5. **Test-first (TDD)** in `_stg__models.yml`: `unique` + `not_null` on the primary key
   (players/sessions/transactions); the affiliate has **no primary key** (conflated grain,
   [ADR-0006](0006-data-contract-and-assumptions.md)) so `not_null` only, its grain is resolved in
   Silver; `accepted_values` on `transaction_type` / `device` / `country`; `amount > 0` and counts
   `>= 0`; timestamps **not in the future**; and **not-null-after-`SAFE_CAST`** (the drift catcher, i.e.
   `not_null` on every typed column). The category and key checks are built-in generic tests; the value
   and temporal assertions are **singular tests** (pure SQL, one failing-row query each).
6. **Boundary.** Bronze does rename + cast + audit passthrough **only**. Email lowercasing, referential
   integrity, the funnel rules (`ftd <= registrations`), the real first deposit and attribution are
   **Silver**; surrogate keys and fraud signals are **Gold**.

### Considered and deferred
- **Model contracts** (`contract: {enforced: true}`) on the `stg_` models would also enforce output
  column names and types at build time (an antidote to silent column-misalignment). Deferred as a
  go-beyond: the explicit `SELECT` already breaks on a dropped column and ignores a new one, and common
  practice reserves enforced contracts for the Gold interface while staging tolerates additive drift.
- **Defensive deduplication** (`qualify row_number()` over the key) is a standard staging function, but
  Q5 shows zero duplicate keys, so it is a documented guard, not needed for this data.

## Consequences
- The four `stg_` models are uniform and predictable: read one and you know them all.
- A bad batch is flagged by a failing test, not crashed (`SAFE_CAST` nulls the bad value). Staging is the
  single place that owns correct types, so autodetect's guesses (money as FLOAT included) never reach
  Silver. (A stricter ingestion could load the raw as all-STRING - the Databricks practice - and hand all
  typing to staging; we use autodetect plus defensive `SAFE_CAST`, which catches the mistake either way.)
- The Bronze tests pass on this clean synthetic data (they are **guards**); the inconsistencies that do
  fail (`ftd > registrations`, transactions before `created_at`) are asserted in **Silver**.
- `dbt_utils` and `dbt-expectations` are declared in `packages.yml` for the layers that need them.
