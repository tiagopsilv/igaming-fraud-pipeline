# ADR-0006 - Data contract and core assumptions

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `exploration/explore_contract.py` - establishes that the source timestamps are all
  **naive** (no offset/`Z`); the three event/entity tables have **unique keys with no hidden logical
  duplicates** (0 duplicate sessions, 0 duplicate transactions); the affiliate table has a **conflated
  grain** (its funnel metrics are affiliate-level - `clicks` averages ~100 and *varies per row even
  for the same player*, ruling out both a per-player record and denormalized affiliate totals - with
  no reporting-period key); `player_id` is **1:1 with email** (600/600); and the transaction types are
  only `deposit / withdraw / bet` (no bonus or chargeback).

## Context
Before modeling, the assumptions that bind every downstream table must be explicit. A data contract
turns implicit assumptions into stated ones, and **declaring the grain is the single most important
modeling decision** - what does one row represent?

## Decision - the contract
1. **Grain per table.** `players` = one player · `sessions` = one session · `transactions` = one
   transaction - each has a unique key and no hidden logical duplicates. `affiliate_cpa_ftd` has a
   **conflated grain**: its funnel counts (`clicks`, `registrations`, `ftd`) are affiliate-level
   (magnitude ~100 clicks; they vary per row even for the same player), carried on a per-player-tagged
   row with no reporting-period key - so it is neither a clean per-player record nor denormalized
   affiliate totals. Its counts are therefore **never summed per row**; attribution is resolved in
   Silver ([ADR-0002](0002-resolve-affiliate-attribution-in-silver.md) / [ADR-0004](0004-affiliate-attribution-rule.md)).
2. **Timezone = UTC.** All source timestamps are naive, so they are cast to `TIMESTAMP` and
   interpreted as **UTC** (assumption: the source clock is UTC; in production the source should emit
   ISO-8601 with `Z`). `players.created_at` is date-only, so first-deposit timing is derived from the
   transactions, not the registration date.
3. **"Account" = `player_id`** (1:1 with email). A natural person may hold several accounts - that is
   the multi-accounting fraud we look for, inferred from shared `ip`/`device`, not a hard key.
4. **Fraud scope (boundary only).** Fraud detection is the objective of the **Gold layer**, where the
   specific signals are designed and discovered. The contract fixes only the boundary: the data has
   `deposit / withdraw / bet` transactions plus session and affiliate context, so **bonus abuse and
   chargeback fraud are out of scope** (no such data). As the sample is synthetic, whatever signals
   are built are production-grade logic, not fraud claimed to be found. *(The specific signals are
   deliberately not enumerated here; they belong to the Gold phase.)*

## Consequences
- Bronze casts every timestamp to a UTC `TIMESTAMP`; the grain is enforced by dbt `unique`/`not_null`
  tests on `player_id`, `session_id`, `transaction_id`.
- The Gold fraud layer builds only the computable signals, with an honest scope note.
- This contract is the shared reference for the Silver and Gold models.
