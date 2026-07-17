# Source-to-Target Mapping (STTM)

How each source column becomes a modeled column, and the rule that transforms it. Rules follow the
data contract (ADR-0006) and the layer decisions (ADR-0004/0005/0007/0008).

Every raw table also carries two audit columns from ingestion (ADR-0005): `_ingested_at`, `_source_file`.

### `dim_player` (SCD Type 1 - ADR-0003)
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `player_id` | `players.player_id` | passthrough (primary key) | Silver |
| `email` | `players.email` | lowercase (normalize, not dedup) | Silver (ADR-0006) |
| `city` | `players.city` | passthrough | Bronze |
| `created_at` | `players.created_at` | cast to DATE, treated as UTC | Bronze (ADR-0006) |
| `acquisition_country` | `affiliate_cpa_ftd.country` (via attribution) | country of the attributed affiliate row: the acquisition, not an affiliate attribute | Silver (ADR-0004) |

### `dim_affiliate` (grain = 1 affiliate)
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `affiliate_id` | `affiliate_cpa_ftd.affiliate_id` | distinct affiliate list (the only clean affiliate-level attribute the source has) | Silver |

The source's other affiliate columns are **per-acquisition, not per-affiliate**, so they do not belong
on this dimension. `country` varies by player (one affiliate spans several countries), and the funnel
counts (`clicks / registrations / ftd / cpa_value`) are row-level and are **never** summed onto the
affiliate (conflated grain, ADR-0006). Which affiliate a player belongs to is resolved in Silver by
`int_player_affiliate_attribution` (claim-FTD gated on a real deposit, ADR-0004).

### `dim_date`
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `date_key`, calendar attrs | derived from the timestamps | date spine (seed / generated) | Gold |

### `fct_transactions` (grain = 1 transaction; partition `DATE(txn_ts)`, cluster `player_id` - ADR-0007)
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `transaction_id` | `transactions.transaction_id` | passthrough (primary key) | Bronze |
| `player_id` | `transactions.player_id` | foreign key to `dim_player` | Bronze |
| `transaction_type` | `transactions.type` | accepted values: `deposit / withdraw / bet` | Bronze |
| `amount` | `transactions.amount` | cast to NUMERIC (money, never FLOAT) | Bronze (ADR-0006) |
| `txn_ts` | `transactions.timestamp` | cast to TIMESTAMP, UTC (partition key) | Bronze (ADR-0006) |

### `fct_sessions` (grain = 1 session; partition `DATE(session_ts)`, cluster `player_id`)
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `session_id` | `sessions.session_id` | passthrough (primary key) | Bronze |
| `player_id` | `sessions.player_id` | foreign key to `dim_player` | Bronze |
| `ip` | `sessions.ip` | passthrough | Bronze |
| `device` | `sessions.device` | passthrough (degenerate dimension) | Bronze |
| `session_ts` | `sessions.timestamp` | cast to TIMESTAMP, UTC (partition key) | Bronze |

### `int_player_first_deposit` (Silver helper - the real FTD)
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `player_id`, `first_deposit_ts` | `transactions` where `type = deposit` | `MIN(timestamp)` per player = the real FTD | Silver (ADR-0004) |

### `fct_fraud_signals` (grain = 1 player - signals designed in the Gold phase)
| Target | Source | Rule | Layer |
|--------|--------|------|-------|
| `player_id` | `dim_player` | per player | Gold |
| fraud flags + `risk_value` | sessions / transactions / affiliate context | multi-account, AML, affiliate ghost-FTD (rules defined when the Gold layer is built) | Gold |
