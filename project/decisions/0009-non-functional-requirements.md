# ADR-0009 - Non-functional requirements (freshness, quality, cost, reliability)

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `exploration/explore_nfr.py` - derives the targets from the data: the timestamp
  granularity (`sessions` sub-second, `transactions` second, `players` date-only) bounds achievable
  freshness; the measured baseline of the hard rules (referential integrity 100%, `amount > 0` 100%,
  `ftd ≤ registrations` 83%, no-transaction-before-`created_at` 81%) sets the quality targets; and
  the volume (~0.9 MB) puts it well inside the BigQuery free tier.

## Context
The product promise is accurate, up-to-date data, so the pipeline needs explicit non-functional
targets. Best practice is to set them from a **measured baseline** (not a wish), and to distinguish
the external promise (**SLA**) from the internal target with a buffer (**SLO**).

## Decision - the NFR / SLO sheet
| Dimension | SLO target | Baseline / justification |
|-----------|-----------|--------------------------|
| Freshness - `sessions` | ≤ 1h (P95 ≤ 45 min) | sub-second granularity → near-real-time capable |
| Freshness - `transactions` | ≤ 1h | second-level granularity |
| Freshness - `players` / `affiliate` | ≤ 24h | date-only / no watermark → daily cadence ([ADR-0008](0008-load-strategy-per-source.md)) |
| Quality - referential integrity | 100% | baseline 100%; dbt `relationships` test blocks the pipeline |
| Quality - `amount > 0` | 100% | baseline 100%; dbt test |
| Quality - `ftd ≤ registrations` | 100% | baseline 83% (synthetic); dbt custom test exposes it |
| Quality - no tx before `created_at` | 100% | baseline 81% (synthetic); dbt custom test |
| Cost | ≤ free tier (**$0**) | ~0.9 MB ≪ 10 GB / 1 TB; guardrails: partition pruning + `require_partition_filter` |
| Reliability | idempotent + retries + alert | `merge` / `WRITE_TRUNCATE`; DAG retries; failure webhook |

Freshness checks run at **2× the SLA frequency**. Batch (Airflow) is the right cost/latency point:
it delivers most of the value of streaming at a fraction of the cost - real-time is out of scope.

## Consequences
- The quality SLOs become dbt tests that **fail the pipeline** on violation (Silver/Gold); the
  freshness SLOs become source-freshness + monitoring checks (observability).
- The cost guardrails (`require_partition_filter`, `maximum_bytes_billed`) prevent accidental full scans.
- Targets are realistic because they start from the measured baseline, not an aspiration.
