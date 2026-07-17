# ADR-0003 - SCD Type 1 for `dim_player`

- **Status:** Accepted
- **Date:** 2026-07-16
- **Evidence:** `exploration/arch_discovery.py` - Q3 shows `players` has no `updated_at` (columns are
  only `player_id, email, city, created_at`), so change history cannot be tracked.

## Context
`dim_player` is built from the `players` source, which has only `player_id`, `email`, `city`, and
`created_at`. There is **no `updated_at`** or any other change-tracking column, and `created_at` is
immutable. Without a way to detect attribute changes, historical (Type 2) tracking is not possible.

## Decision
Model `dim_player` as a **Slowly Changing Dimension Type 1** (overwrite on change). The dimension
reflects the current state of each player; no history is kept.

## Consequences
- Simple and correct for the data actually available.
- No historical attribute analysis (e.g. a player's city at the time of a past transaction).
- Documented as a data limitation. If the source later exposes `updated_at`, revisit this ADR and
  supersede it with a Type 2 / dbt snapshot approach.
