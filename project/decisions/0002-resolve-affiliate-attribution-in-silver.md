# ADR-0002 - Resolve affiliate attribution in the Silver layer

- **Status:** Accepted
- **Date:** 2026-07-16
- **Evidence:** `exploration/arch_discovery.py` - Q4 shows the player↔affiliate many-to-many (504
  players under >1 affiliate) and Q5 measures the fan-out of a naive join (1,800 → 6,148 rows;
  R$2.71M → R$9.30M).

## Context
The `affiliate_cpa_ftd` source has a conflated grain: `clicks`, `registrations`, and `ftd` are
row-level aggregates glued to a random `player_id`, and the same player appears under up to **10**
affiliates (a many-to-many relationship - 504 players are linked to more than one affiliate).

Joining this source naively to a financial fact is dangerous. Measured on the real data, a plain
`transactions × affiliate` join on `player_id` inflates **1,800 → 6,148 rows (3.4×)** and the total
`amount` from **R$2.71M → R$9.30M**. CPA is, by definition, paid once per acquired player.

## Considered options
- **A - Bridge table** with an allocation factor (one row per `player`↔`affiliate` pair; facts point
  to a group key). This is the Kimball-correct pattern for genuine multi-touch attribution.
  *Rejected here:* the source has no timestamp, so time-based (last-touch) allocation is impossible,
  and multi-touch credit is not part of the CPA business model, so it would be over-engineering.
- **B - Resolve to one affiliate per player in the Silver layer** (`int_player_affiliate_attribution`),
  crediting the affiliate tied to the player's real first deposit. **Chosen.**

## Decision
Resolve affiliate attribution to a single affiliate per player in Silver, before any fact touches the
affiliate data. Never sum `clicks` / `registrations` / `ftd` / `cpa_value` across raw rows.

## Consequences
- Eliminates the 3.4× fan-out before it can corrupt any measure.
- Encodes an explicit, documented business rule (auditable in one model).
- Loses multi-touch nuance, acceptable for this dataset; a bridge table is the documented upgrade
  path if multi-touch attribution is ever required.
