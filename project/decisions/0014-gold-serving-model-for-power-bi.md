# ADR-0014 - Gold serving model for Power BI (star schema, Import mode)

- **Status:** Accepted
- **Date:** 2026-07-19
- **Evidence:** `analyses/gold_dashboard_metrics.sql`, run on the **real data**: the headline KPI of each
  panel computes - Affiliate Metrics (CPA owed R$16,505, real revenue R$172,580, **ROI 10.5x**),
  Financial Signals (deposits R$898,037, withdrawals R$967,211, **house net -R$69,175**, 105 low-play
  players). The Fraud Overview KPIs come from `gold_fraud_signal_scan` (ADR-0013).

## Context
The dashboard (**E5**) needs three panels: **Fraud Overview**, **Affiliate Metrics**, **Financial
Signals**. Power BI's VertiPaq engine is optimized for a **star schema** and **Import mode**; the Gold
must serve exactly that, so the report is fast, consistent and offline-demoable.

## Decision
The Gold marts are a **star schema**, consumed by Power BI in **Import mode**:
- **Conformed dimensions:** `dim_player` (SCD-1, ADR-0003), `dim_affiliate`, `dim_date` (a date spine).
- **Facts** (grain = one event), partition by date + cluster by `player_id` (ADR-0007):
  - `fct_transactions` - built from `int_player_ledger`, so it carries the **running balance** (exposure over time).
  - `fct_sessions` - `ip`/`device` per session (the IP/device drill-down).
- **Player / affiliate marts:**
  - `fct_fraud_signals` (ADR-0013) - flags + risk score + value at risk.
  - `agg_affiliate_performance` - per affiliate: qualified FTDs, CPA owed, real revenue, ROI, ghost-FTD.
- **Relationships flow dimensions -> facts** (single direction, no bidirectional); **Import mode** (the
  data is well inside the free tier, so in-memory is fast and needs no live warehouse connection to demo).
- **Panel mapping:**
  - Fraud Overview  <- `fct_fraud_signals` + `fct_sessions` + `dim_player`.
  - Affiliate Metrics <- `agg_affiliate_performance` + `dim_affiliate`.
  - Financial Signals <- `fct_transactions` (+ balance) + `int_player_financials` + `dim_date`.

## Governance (the marts are a public interface)
- **Enforced model contracts** on every mart: the build fails if a column is dropped, renamed or
  retyped, so the schema Power BI imports is guaranteed. This is the recommended practice for models
  relied on downstream.
- A **dbt exposure** (`fraud_dashboard`) declares the report as the consumer of the marts, giving
  end-to-end lineage (source -> Bronze -> Silver -> Gold -> dashboard) and impact analysis
  (`dbt build -s +exposure:fraud_dashboard` rebuilds exactly what the dashboard depends on).

## Consequences
- One semantic model, three panels, all sharing the conformed dimensions - the numbers reconcile across the report.
- The affiliate **funnel** (clicks/registrations) is conflated-grain (ADR-0006), so the panel leads with the
  **reliable attributed metrics** (CPA, ROI, qualified FTDs) and shows the raw funnel with a caveat.
- No data is lost from Bronze/Silver: the facts read the granular layer (`stg_` + ledger); the marts read
  the Silver features. Every panel KPI has a verified source.
