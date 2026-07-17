# ADR-0008 - Load strategy per source (E4)

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `exploration/explore_load_strategy.py` - for each source it checks the control fields
  the data actually offers: `players`, `sessions`, `transactions` each have a **unique key** and a
  timestamp; **none** has an `updated_at` (no change-tracking); and `affiliate` has **no date column
  at all** (no watermark). Those facts decide full vs incremental.

## Context
The case requires a load-strategy definition per source - frequency × full/incremental × control
field × justification. The strategy must follow what each source's data can actually support, not a
one-size rule.

## Decision - the load-strategy table
| Source | Frequency | Load | Control field | Justification |
|--------|-----------|------|---------------|---------------|
| `players` | daily | **full** | - | small dimension; no `updated_at` to drive incremental (SCD-2 in production) |
| `sessions` | hourly / near-real-time | **incremental - `insert_overwrite`** (day partition) | `timestamp` (event time) | high-volume append-only event; `insert_overwrite` avoids per-row `MERGE` cost; reprocess a moving window for late data |
| `transactions` | hourly / daily | **incremental - `merge`** | `transaction_id` (+ `timestamp` watermark) | financial ledger; `merge` is idempotent, so a rerun must **not** duplicate money |
| `affiliate_cpa_ftd` | daily | **full** | - | a restated aggregate with no date column → no watermark is possible; small enough for full |

The incremental strategies are implemented in the dbt **fact models** (`fct_transactions` with `merge`,
`fct_sessions` with `insert_overwrite`); the raw ingestion itself is a small full reload
([ADR-0005](0005-raw-ingestion-idempotent-ndjson.md)). The Airflow DAG schedules follow the frequencies.

## Consequences
- The strategy matches the data: `merge` (idempotent) for money, `insert_overwrite` for high-volume
  events, `full` for the dimension/aggregate that lack a watermark - no forced incremental.
- Late-arriving data is handled by reprocessing a moving window of recent partitions (not `> max(ts)`).
- Production upgrades (documented, not needed for the sample): if `players` gains an `updated_at` it
  moves to SCD-2 / `merge`; if the affiliate report gains a `report_date` it moves to `merge` on
  `(affiliate_id, report_date)`.
