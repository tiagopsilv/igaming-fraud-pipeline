-- Completeness: every player in dim_player must have exactly one row in fct_fraud_signals - no player
-- is silently dropped from the fraud scan (nothing left out). Expect 0 rows.
select p.player_id
from {{ ref('dim_player') }} as p
left join {{ ref('fct_fraud_signals') }} as f using (player_id)
where f.player_id is null
