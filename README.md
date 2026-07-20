# iGaming Fraud-Detection Data Pipeline

A complete data pipeline that ingests four heterogeneous sources (JSON/CSV), models them through a
**Medallion architecture** (Bronze → Silver → Gold) on **BigQuery** with **dbt**, orchestrated by
**Airflow**, and serves fraud signals plus affiliate and financial metrics to a **Power BI** dashboard.

> **New here? Read this file top to bottom** — it walks through the business problem, the architecture,
> what each layer does, the fraud signals, how to run it, and where every piece lives. Design rationale
> for each choice is in the ADRs under [`project/decisions/`](project/decisions/).

---

## 1. The problem

An operator that runs digital platforms receives data about **user acquisition** (via affiliates),
**player behaviour** (login sessions), and **money movements** (deposits, withdrawals, bets). The data
arrives in different formats and must be ingested, cleaned, structured, and made available so analysts can
**detect fraud** and **measure affiliate and financial performance**.

**The four sources:**

| Source | Format | What it is | Used for |
|--------|--------|------------|----------|
| `players` | JSON | player registry (id, email, city, created_at) | the player dimension; registration-burst detection |
| `sessions` | JSON | access sessions (ip, device, timestamp) | suspicious-behaviour signals (IP / device / geography) |
| `transactions` | CSV | money movements (deposit / withdraw / bet, amount) | financial anomalies; the wallet ledger |
| `affiliate_cpa_ftd` | CSV | acquisition by affiliate (clicks, registrations, ftd, cpa_value) | affiliate performance; acquisition-fraud (ghost FTDs) |

---

## 2. Architecture

The pipeline lands the raw files into BigQuery, refines them layer by layer with dbt, and exposes only the
Gold layer to Power BI. Airflow runs the whole thing. Full diagram and source-to-target mapping in
[`docs/architecture.md`](docs/architecture.md).

```
sources ──▶ raw ──▶ Bronze (staging) ──▶ Silver (intermediate) ──▶ Gold (marts) ──▶ Power BI
                    cast / typing        conform + business rules   star schema +
                                                                    fraud signals
```

**What each Medallion layer does:**

| Layer | dbt folder | Materialization | Responsibility |
|-------|-----------|-----------------|----------------|
| **Bronze** | `models/staging/` (`stg_*`) | views | one model per source: cast types (`SAFE_CAST`), fix money to `NUMERIC`, normalize to UTC. No business logic. |
| **Silver** | `models/intermediate/` (`int_*`) | tables | conform identities, apply business rules (real vs qualified FTD, affiliate attribution), build the reusable **wallet ledger** with a running balance. |
| **Gold** | `models/marts/` (`dim_*`, `fct_*`, `agg_*`) | tables | a **star schema** for analytics: dimensions + facts + the fraud-signal and affiliate-performance marts. Only this layer feeds the dashboard. |

The Gold layer is a star schema (dimensions filter facts, one direction): `dim_player` (SCD-1),
`dim_affiliate`, `dim_date`, the facts `fct_transactions` and `fct_sessions`, plus the two serving marts
`fct_fraud_signals` and `agg_affiliate_performance`. Every Gold model carries an **enforced dbt contract**,
and a **dbt exposure** links the marts to the Power BI report for end-to-end lineage.

---

## 3. Fraud detection (the analytical core)

The Gold model `fct_fraud_signals` holds **one row per player** with **ten fraud signals**, each a boolean
with an SQL rule. Five **core** signals combine into a **risk score (0–5)** — the more a player trips, the
higher the confidence, which is the standard way to cut false positives. Five **secondary** signals add
context without inflating the score. `value_at_risk` = the money a player withdrew (the exposure).

| Signal | Type | Source | What it detects |
|--------|------|--------|-----------------|
| `s_ghost_ftd` | core | affiliate + transactions | affiliate claimed an FTD for a player who never really qualified |
| `s_aml_low_play` | core | transactions | deposited, barely bet, then withdrew (money-laundering shape) |
| `s_ip_velocity` | core | sessions | more than 10 distinct IPs (VPN / bot / shared account) |
| `s_ledger_anomaly` | core | transactions | money left the wallet before the first deposit |
| `s_net_negative` | core | transactions | withdrew more than deposited |
| `s_structuring` | secondary | transactions | many round-number deposits (threshold avoidance) |
| `s_geo_conflict` | secondary | affiliate | tagged under more than one acquisition country |
| `s_device_takeover` | secondary | sessions | 3+ distinct devices |
| `s_reg_velocity` | secondary | players | registered during a burst day (top decile) |
| `s_dormant` | secondary | sessions | long dormant span then reactivation |

The score buckets into a categorical `risk_tier` (Critical / High / Medium / Low / No alert) computed in
Gold, so risk reads by **label**, not colour alone. Rationale: [ADR-0013](project/decisions/0013-gold-fraud-signals-risk-score.md).

> **Honesty note:** the sample data is synthetic and random, so any raised flag is coincidental. What is
> real is the **production-grade logic** and the honest count — never a claim of "fraud found".

---

## 4. Load strategy (per source)

Each source gets the load type its data can actually support — not a one-size rule. Full table and evidence
in [ADR-0008](project/decisions/0008-load-strategy-per-source.md).

| Source | Frequency | Load type | Control field | Why |
|--------|-----------|-----------|---------------|-----|
| `players` | daily | **full** | — | small dimension; no `updated_at` to drive incremental |
| `sessions` | hourly / near-real-time | **incremental — `insert_overwrite`** (day partition) | `timestamp` | high-volume append-only events; avoids per-row `MERGE` cost |
| `transactions` | hourly / daily | **incremental — `merge`** | `transaction_id` | financial ledger; `merge` is idempotent, so a rerun never duplicates money |
| `affiliate_cpa_ftd` | daily | **full** | — | restated aggregate with no date column → no watermark possible |

The two incremental strategies are implemented in code in the Gold facts (`fct_transactions` uses `merge`;
`fct_sessions` uses `insert_overwrite`, guarded by `is_incremental()`).

---

## 5. Orchestration & observability

- **Airflow** (Astro Runtime + **Cosmos**) runs `ingest → source freshness → dbt build`. Cosmos renders
  **every dbt model and test as its own task**, so lineage, retries, and failures are visible per model
  (not one opaque `dbt build`). Credentials come from an Airflow connection — no secrets in code.
  [ADR-0015](project/decisions/0015-orchestration-airflow-cosmos.md).
- **Observability** is instrumented with **Elementary**: it logs every model run and test result, and adds
  `schema_changes` (drift) monitors on all four sources plus `volume_anomalies` on the high-volume events,
  on top of dbt **source freshness**. [ADR-0016](project/decisions/0016-observability-with-elementary.md).

---

## 6. The dashboard

A Power BI report over the Gold star schema (Import mode), in **four pages**: **Fraud Overview**,
**Acquisition & Retention**, **Affiliate Metrics**, **Financial Signals**. Delivered as
`dashboard/igaming_fraud_dashboard.pbix` with a custom light theme, data bars, and the risk-tier label.
Design, layout, and every visual's measure are documented in [`docs/dashboard.md`](docs/dashboard.md).

---

## 7. How to run

**Requirements:** Python 3.11+, Docker Desktop, the [Astro CLI](https://www.astronomer.io/docs/astro/cli/overview),
and a BigQuery project with a service-account key.

```bash
# 1. Install and get to know the data (offline)
pip install -r requirements-dev.txt
python exploration/explore_sources.py

# 2. Land the raw sources into BigQuery
#    (set your project in config.toml and point it at your service-account key first)
python ingestion/load_raw.py

# 3. Run the unit tests
pytest tests/ -q
```

**Run the whole pipeline (Airflow) with one command** — `dev.sh` syncs the dbt project into the Astro
project, starts Airflow, waits until it is healthy, and prints the URL (login `admin` / `admin`):

```bash
./dev.sh up          # start Airflow, ready to run
./dev.sh rebuild     # re-sync + restart + trigger the pipeline (after changing dbt models)
./dev.sh status      # containers + DAG + last run state
```

`make up` / `make rebuild` do the same where GNU make is available. To run dbt on its own:
`cd dbt && dbt deps && dbt build --profiles-dir .`.

---

## 8. Testing

Two complementary test layers (dbt best practice):

- **Unit tests** (`_*__unit_tests.yml`) validate the transformation **logic** on static fixtures —
  the qualified-FTD baseline, single-winner attribution, Net Deposit, the wallet running balance, the fraud
  risk score, and affiliate ROI. They test the code, independent of the warehouse data.
- **Data tests** — dbt generic tests (unique / not_null / accepted_values / relationships / contracts) plus
  business-rule assertions on the real data (the ledger reconciles, the risk score matches its flags, every
  player has a fraud profile, CPA is credited only for qualified players).
- **Python** ingestion is covered by `pytest`; SQL is linted with **sqlfluff** and Python with **ruff**.

---

## 9. Repository layout

```
data/            # synthetic source sample (reproducible; production would land in cloud storage)
config.toml      # public pipeline configuration (env-overridable; no secrets)
ingestion/       # land the sources into BigQuery — NDJSON + audit columns + idempotent load
dbt/             # dbt project: Bronze (staging) + Silver (intermediate) + Gold (marts) + tests
airflow/         # Astro + Cosmos project: the orchestration DAG
dashboard/       # the Power BI .pbix report
exploration/     # one-time discovery scripts that back the design decisions
docs/            # architecture diagram + source-to-target mapping + dashboard design
tests/           # Python unit tests (pytest)
project/         # ROADMAP · STATUS · CHANGELOG · decisions (ADRs)
dev.sh, Makefile # one-command local pipeline
```

---

## 10. Design decisions & a note on the data

Every architecture choice is written up as an **evidence-based ADR** in
[`project/decisions/`](project/decisions/) — each one cites the exploration script that demonstrates it.
Start with [ADR-0001 (Medallion)](project/decisions/0001-medallion-architecture.md) and
[ADR-0013 (fraud signals)](project/decisions/0013-gold-fraud-signals-risk-score.md).

Discovery established that the four sample datasets are **synthetic and random** (zero nulls, inverted money
flow, impossible sequences such as withdrawals without deposits). The pipeline is therefore built to be
correct on real data and honest about the sample.

### Limitations (what the data does not support)
Some standard iGaming metrics **cannot** be computed from the four sources, and are deliberately left out
rather than faked:
- **NGR / GGR / RevShare** need bonus, tax, and per-bet outcome (win/loss) data the sources lack.
- **LTV** needs a longer horizon than the sample window (ARPU and month-over-month **Retention** are
  computed; a full LTV is not).
- **Chargeback / Rollover / Bonus abuse** have no supporting data (fraud scope is bounded in ADR-0006).

Affiliate **Real Revenue** is reported as **Net Deposit** (deposits − withdrawals), an honest proxy, not NGR.

---

**Planning & history:** [Roadmap](project/ROADMAP.md) · [Status](project/STATUS.md) ·
[Changelog](project/CHANGELOG.md) · [Decisions (ADRs)](project/decisions/)
