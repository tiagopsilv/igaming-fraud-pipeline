-- Fraud scoring integrity (ADR-0013): risk_score must equal the count of the FIVE core signals.
-- If they disagree, the score is wrong and the Fraud Overview panel would mislead. Expect 0 rows.
select player_id, risk_score
from {{ ref('fct_fraud_signals') }}
where risk_score != (
      cast(s_ghost_ftd     as int64)
    + cast(s_aml_low_play  as int64)
    + cast(s_ip_velocity   as int64)
    + cast(s_ledger_anomaly as int64)
    + cast(s_net_negative  as int64)
)
