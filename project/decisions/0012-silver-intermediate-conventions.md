# ADR-0012 - Silver intermediate conventions and the wallet ledger

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `analyses/silver_discovery.sql`, `analyses/silver_feature_scan.sql` and
  `analyses/silver_ledger_reconciliation.sql`, run with `dbt show` on the **real BigQuery data**. They
  establish: email is casing only (600 distinct before and after lowercasing), 0 referential orphans,
  the real (379) and qualified (227) FTD, the reusable per-player features (net deposit, bet_ratio, IP
  counts), and the wallet-ledger reconciliation (**371 players transact before any deposit**).

## Context
Silver ([ADR-0001](0001-medallion-architecture.md)) conforms, joins and derives the business-ready
building blocks. Beyond the specific decisions already recorded (attribution [ADR-0002](0002-resolve-affiliate-attribution-in-silver.md)/[0004](0004-affiliate-attribution-rule.md),
qualified FTD [ADR-0011](0011-attribution-gates-on-qualified-ftd.md)), the layer needs its conventions
fixed so the `int_` models are uniform and the Gold layer and dashboard can rely on them.

## Decision - the conventions
1. **Materialize `int_` as tables** (not ephemeral). The dbt guide leans ephemeral for pure building
   blocks, but a Medallion Silver is **persisted, queryable and testable** - the ledger and the feature
   rollups are inspected directly and consumed by many Gold marts, so tables win over ephemeral here.
2. **Conform, do not dedup.** Email is lowercased (normalization); there are no real duplicate accounts.
3. **Reusable feature building blocks.** Per-player rollups are computed once in Silver and reused by
   Gold and the dashboard (DRY): `int_player_financials` (deposits/withdrawals/bets, **net deposit**,
   **bet_ratio**) and `int_player_activity` (sessions, **distinct IPs/devices**, active span). The
   feature is Silver; the fraud **flag** built on it (`bet_ratio < 0.2`, `IP > 10`) is Gold.
4. **Wallet ledger reconciliation.** `int_player_ledger` reconstructs the running balance per player
   (deposit `+`, withdraw/bet `-`, ordered in time). The integrity rule is that the balance never goes
   negative - you cannot spend money you never had. *Caveat: the data has bet amounts but no bet
   outcomes (win/loss), so bets are a conservative pure outflow; the unambiguous violation is money-out
   before the first deposit (371 players), which holds regardless of wins.*
5. **Test strategy - error vs warn.** Structural/integrity tests (`unique`, `not_null`, `relationships`)
   are `error`; they hold. The business-rule data-quality tests (funnel logic, no transaction before
   signup, ledger integrity) are `severity: warn`: the synthetic sample violates them by design, so they
   **surface the count** (344 / 139 / 344 / 372) instead of failing the build. In production they error.

## Consequences
- The seven `int_` models are uniform, tested and documented; the Gold star schema and the fraud signals
  build directly on them (features + ledger), avoiding recomputation.
- The ledger gives an audit-replayable reconciliation - the strongest data-quality finding, and one that
  maps to real operator practice.
- `dbt build` stays green (`ERROR=0`); the four warnings are the surfaced data-quality findings, not failures.
