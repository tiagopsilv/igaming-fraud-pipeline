# ADR-0013 - Gold fraud signals and the multi-signal risk score (R2)

- **Status:** Accepted
- **Date:** 2026-07-19
- **Evidence:** `analyses/gold_fraud_signal_scan.sql`, run with `dbt show` on the **real BigQuery data**.
  Five **core** signals, each with its reach and value at risk - affiliate ghost-FTD (355 players /
  R$583,716), AML low-play (105 / R$249,504), IP velocity (42 / R$69,232), ledger anomaly (372 /
  R$720,922), net-negative (278 / R$799,085); the high-confidence multi-signal set (risk score >= 2):
  **362 players, R$826,165 at risk**. Five **secondary** signals walk the rest of the fraud catalog:
  structuring (0), geo conflict (479), device takeover (413), registration velocity (287), dormant
  reactivation (114).

## Context
The case requires at least two fraud signals in the Gold layer (**R2**), each with an SQL rule and a
value at risk. Market practice is to combine several signals into a single **risk score** rather than
relying on any one - this cuts false positives and gives an interpretable audit trail.

## Decision
Materialize **`fct_fraud_signals`** at grain = one player, built on the Silver features and the ledger:
1. **Five signals**, each a boolean flag with an SQL rule:
   - **affiliate ghost-FTD** - an affiliate claims a first deposit for a player who never QUALIFIED (ADR-0011).
   - **AML low-play** - `bet_ratio < 0.2` AND withdrew (deposit, barely bet, cash out).
   - **IP velocity** - `> 10` distinct IPs (VPN/bot foot-printing).
   - **ledger anomaly** - money-out before the first deposit (the reconciliation red flag, ADR-0012).
   - **net-negative** - withdrew more than deposited (one-and-done / house-loses).
2. A **multi-signal risk score** = the count of **core** signals a player trips; a score `>= 2` is the
   high-confidence set. This is the standard way to reduce the false positives a single signal produces.
3. **`value_at_risk`** per player = the amount withdrawn (money exposed to loss).
4. The thresholds (`bet_ratio` 0.2, `IP` 10) are parametrizable premises, not universal truths.
5. **Five secondary signals** cover the rest of the catalog as logic-ready flags, computed but kept
   **out of the score**: structuring (>= 3 round deposits), geo conflict (> 1 acquisition country),
   device takeover (>= 3 distinct devices), registration velocity (a burst day), dormant reactivation
   (active span > 60d). They are carried on `fct_fraud_signals` for drill-down, not scored, because on
   this data they are thin or noisy: structuring is empty; device/registration are inflated by low
   cardinality (only three device types, few distinct registration days); geo conflict (479) and
   dormancy (114) reconcile with the Silver findings.

## Consequences
- `fct_fraud_signals` feeds the **Fraud Overview** panel (suspicious accounts, value at risk, risk score)
  and cross-references `dim_player` / `fct_sessions` for the IP/device drill-down.
- The multi-signal score is the actionable number; the individual flags are the audit trail.
- **Honest framing (project rule):** the sample is synthetic/random, so the hits are coincidental - this
  is production-ready logic and an honest count, never "fraud found". IP-sharing is ~0 in the data, so the
  multi-account angle is logic-ready but empty; it is reframed as IP velocity per player.
