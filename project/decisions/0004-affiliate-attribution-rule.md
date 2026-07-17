# ADR-0004 - Affiliate attribution rule (claim-FTD gated on a real deposit)

- **Status:** Accepted
- **Date:** 2026-07-16
- **Evidence:** `exploration/compare_attribution.py` - measures the three candidate rules (R1/R2/R3):
  players attributed and CPA implied, plus the 209 ghost FTDs and R$16,395 overcount that gating on
  a real deposit removes.
- **Refines:** [ADR-0002](0002-resolve-affiliate-attribution-in-silver.md) (which decided *where* to
  resolve attribution - the Silver layer). This ADR specifies the exact rule.

## Context
Attribution assigns one affiliate (and therefore the CPA cost) to each player. The affiliate source
has **no timestamp** and a conflated grain (a player appears under up to 10 affiliates), so a true
time-based last-touch is not recoverable. A deterministic, defensible rule is required instead.

Three computable rules were measured on the real data:

| Rule | Definition | Players attributed | CPA implied |
|------|------------|--------------------|-------------|
| R1 | first affiliate row by file order | 581 | 32,845 |
| R2 | affiliate that claims the FTD (`ftd > 0`), deterministic tiebreak | 575 | 43,890 |
| **R3** | R2 **gated on the player having a real deposit** | **366** | **27,495** |

## Decision
Use **R3**: for each player with a **real first deposit** (derived from `transactions`), credit the
affiliate whose row claims the FTD (`ftd > 0`), breaking ties by highest `cpa_value` then lowest
`affiliate_id`. Players without a real deposit are credited to no affiliate (no CPA). Never sum
affiliate metrics across raw rows.

## Consequences
- CPA is paid only for real conversions: **209 ghost FTDs** (claimed but never deposited) are
  excluded, avoiding **R$16,395** (~37%) of inflated CPA versus R2. Attribution doubles as an
  anti-fraud gate.
- Deterministic and reproducible (stable tiebreak) - safe for repeated pipeline runs.
- Known limitations (documented as assumptions): without a timestamp the "claim-FTD" affiliate is a
  proxy, not ground truth - for 307 real-FTD players more than one affiliate claims the FTD; and 9
  real-FTD players have no affiliate row (organic / data gap). With a real tracking link + timestamp
  this rule should be superseded by the true referrer / last-touch.
- Implemented by the Silver model `int_player_affiliate_attribution`.
