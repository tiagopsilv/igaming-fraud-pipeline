# ADR-0016 - Observability instrumented with Elementary

- **Status:** Accepted
- **Date:** 2026-07-20
- **Evidence:** the Elementary package built its models and logs on the **real BigQuery data** - after a
  `dbt build`, `dbt_run_results` holds 190 rows and `elementary_test_results` 105 rows; the monitoring
  tests run green (`schema_changes` on all four sources, `volume_anomalies` on `transactions`/`sessions`).

## Context
[ADR-0009](0009-non-functional-requirements.md) *identified* the observability points (freshness, volume,
schema drift, null/anomaly, lineage) and chose a **proportional stack** (dbt tests + dbt-expectations +
Elementary). This ADR takes that from *identified* to *instrumented*: observability matters, and
"identified but not built" is weaker than a monitor that actually runs.

## Decision
Instrument observability with the **Elementary** dbt package:
1. **Run/test logging** - Elementary's `on-run-end` hooks write every model run and every test result to
   an `analytics_elementary` schema, so pipeline health is queryable data (not just console output).
2. **Schema-drift monitor** - `elementary.schema_changes` on all four sources: fails if a column is
   added, removed or retyped (the silent-drift failure mode).
3. **Volume anomaly monitor** - `elementary.volume_anomalies` (keyed on `_ingested_at`) on the high-volume
   events (`transactions`, `sessions`): flags a row-count outside the learned norm (a truncated load).
4. **Alerts** - the `analytics_elementary.alerts_*` views surface failures as data (webhook-ready); the
   `edr` CLI renders the HTML observability report.

The stack stays **proportional**: dbt-native, versioned, no extra infrastructure. Monte Carlo / Soda would
be over-engineering at this scale (noted as a scale path in ADR-0009).

## Consequences
- Freshness (source freshness, already configured), schema drift and volume are now **active monitors**,
  not just documented points - observability is instrumented.
- **Anomaly monitors learn from history:** on a single run they calibrate and pass; the value is the
  instrumentation being in place, which the honest framing states.
- `dbt build` now also builds Elementary's models and logs results (a longer but richer run).
