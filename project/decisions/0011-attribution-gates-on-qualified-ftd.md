# ADR-0011 - Affiliate attribution gates on the QUALIFIED FTD (deposit + bet baseline)

- **Status:** Accepted
- **Date:** 2026-07-17
- **Evidence:** `analyses/silver_discovery.sql` (Step 4), run with `dbt show` on the **real BigQuery data**:
  of the **379** players with a real deposit, only **227** also bet at least the baseline. The gap is
  exactly the set that deposited but never qualified.
- **Refines:** [ADR-0004](0004-affiliate-attribution-rule.md), which gates CPA on a *real deposit*. This
  ADR tightens the gate to the domain-correct definition.

## Context
The **glossary** defines the affiliate payout precisely: CPA is paid for a **Qualified FTD** - a player
who **deposits AND bets the baseline**, not merely anyone who deposits. `affiliate_cpa_ftd` is a CPA
dataset, so the attribution and CPA logic must follow that definition. ADR-0004 gated on a *real deposit*
(379 players); the glossary's qualified FTD is stricter, and the data can express it because we have both
`deposit` and `bet` transactions.

## Decision
Attribution and CPA gate on the **qualified FTD**, resolved in Silver:
1. A player qualifies when they have a **real deposit** AND their **total bets `>=` baseline**.
2. The **baseline is a parametrizable assumption** (a dbt `var`, with an example default of 50 in the
   discovery); in production the operator sets the real baseline (the glossary uses a small per-deposit figure).
3. `int_player_qualified_ftd` produces the qualified set; `int_player_affiliate_attribution` (ADR-0004's
   claim + deterministic tiebreak) then credits the affiliate only for **qualified** players.
4. The "real deposit" gate (ADR-0004) stays the **floor**; qualified is the domain-accurate layer on top.

## Consequences
- CPA is credited only for players who actually qualified: on this sample, **227 of 379** deposit-holders
  (baseline 50), so a deposit-only view over-counts CPA by the un-qualified remainder. Attribution becomes
  domain-accurate and speaks the language of the affiliate business.
- The baseline is **explicit and tunable**, so the model states its assumption instead of hiding it.
- As the sample is synthetic, this is production-grade logic; the exact counts are not a real finding.
- Testable in Silver: `qualified <= deposited <= players`, and the qualified set drives the CPA measures.
