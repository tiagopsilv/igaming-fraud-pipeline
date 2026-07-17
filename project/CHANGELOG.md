# Changelog

Milestones delivered and findings made, newest first. Format inspired by
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### 2026-07-17 - Architecture diagram + source-to-target mapping
**Added**
- `docs/architecture.md` - the **E1** architecture diagram (Mermaid C4 / data-flow: sources →
  ingestion → Bronze → Silver → Gold → Power BI, orchestrated by Airflow).
- `docs/source_to_target_mapping.md` - how each source column maps to a modeled column and the rule
  that transforms it, tracing back to the decisions (ADR-0004/0005/0006/0007/0008).
- These complete the architecture specification; the build (dbt models) is next.

### 2026-07-17 - Non-functional requirements
**Delivered**
- The non-functional requirements (freshness, quality, cost, reliability SLOs), locked as **ADR-0009**.

**Discovered (targets from a measured baseline)**
- `exploration/explore_nfr.py`: timestamp granularity bounds freshness (sessions near-real-time,
  transactions hourly, players/affiliate daily); the hard-rule baseline (referential integrity and
  `amount > 0` at 100%, `ftd ≤ registrations` at 83%, no-tx-before-`created_at` at 81%) sets the
  quality SLOs; and the ~0.9 MB volume keeps cost inside the BigQuery free tier ($0).

### 2026-07-17 - Load strategy (E4)
**Delivered**
- The load-strategy table (deliverable **E4**), locked as **ADR-0008**: per source, its frequency,
  full vs incremental, control field, and rationale.

**Discovered (decides full vs incremental)**
- `exploration/explore_load_strategy.py`: `players`/`sessions`/`transactions` each have a unique key
  and a timestamp, but none has an `updated_at`; `affiliate_cpa_ftd` has no date column at all. So
  the money ledger loads with an idempotent `merge`, the high-volume sessions with `insert_overwrite`,
  and the dimension/aggregate that lack a watermark load `full`.

### 2026-07-17 - Gold star schema & physical design
**Delivered**
- The Gold dimensional model and its BigQuery physical design, locked as **ADR-0007**: dimensions
  and facts, partition-by-date + cluster-by-`player_id`, and materialization per layer.

**Discovered (justifies the design)**
- `exploration/explore_star_schema.py`: the descriptive entities are small (dimensions → full
  tables); the facts' date spans and `player_id` cardinality justify partitioning by date and
  clustering by `player_id`; and referential integrity to the player dimension holds.

### 2026-07-17 - Data contract
**Delivered**
- The data contract, locked as **ADR-0006**: grain per table, a UTC timezone standard, and
  "account" = `player_id` - the assumptions that bind the modeling. (Fraud scope is bounded here -
  bonus/chargeback are out of scope; the signals themselves are a Gold-layer design.)

**Discovered (binds the modeling)**
- `exploration/explore_contract.py`: the source timestamps are naive (standardized to UTC); the
  three event/entity tables have clean unique-key grains, while the affiliate table has a conflated
  grain (affiliate-level funnel carried on a per-player-tagged row); and `player_id` is 1:1 with email.

### 2026-07-17 - Ingestion layer
**Delivered**
- Ingestion layer, built test-first: `data/` (synthetic sample) + `config.toml` (public,
  env-overridable configuration) + `ingestion/load_raw.py`, which normalizes each source to NDJSON
  with audit columns and loads it into the `raw` dataset with an idempotent `WRITE_TRUNCATE`. Covered
  by `tests/test_load_raw.py` (pytest) and linted with ruff (config in `pyproject.toml`). See **ADR-0005**.
- Living project plan: `ROADMAP.md`, `README.md`, and the `project/` folder.

**Discovered (drives the design)**
- Ingestion-readiness analysis (`exploration/explore_ingestion.py`): the source files use CRLF, so
  the loader writes NDJSON as LF; the JSON is flat with a single schema and the CSVs have no ragged
  rows or embedded newlines - a clean, safe load. Volume baseline: 600 / 4000 / 1800 / 2000.

### 2026-07-16 - Foundation, discovery & architecture
**Delivered**
- Cloud foundation: BigQuery project (free tier), least-privilege service account, dbt connected.
- Data discovery across the four sources (`exploration/`), each finding traced to an assumption.
- Architecture captured as evidence-based ADRs (each cites the exploration script that demonstrates
  it) and a `project/` management folder (STATUS, ROADMAP, CHANGELOG, decisions/).

**Discovered (fraud, risk & data quality)**
- The sample data is synthetic and random (zero nulls, inverted money flow, impossible sequences), so
  the fraud signals are designed as production-grade logic - a deliberate, analytical framing.
- Affiliate acquisition is many-to-many (a player under up to 10 affiliates); a naive join would
  inflate the amount 3.4×. Resolving attribution in Silver excludes **209 ghost FTDs** and
  **R$16,395 (~37%)** of inflated CPA.
- Data-quality signals that become tests: `ftd > registrations` (17%), `registrations > clicks` (7%),
  uppercase emails (22%), transactions before account creation (19%), JSON arrays, untyped amounts.

**Decided (evidence-based ADRs)**
- 0001 Medallion architecture · 0002 affiliate attribution in the Silver layer ·
  0003 SCD Type 1 for `dim_player` · 0004 attribution rule (claim-FTD gated on a real deposit).
