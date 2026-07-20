-- CPA integrity (ADR-0011): the qualified FTDs counted across affiliates must equal the number of
-- attributed (qualified) players - no affiliate is credited a CPA for an unqualified player. Expect 0 rows.
select
    agg_total,
    attr_total
from (
    select
        (select sum(qualified_ftds) from {{ ref('agg_affiliate_performance') }}) as agg_total,
        (select count(distinct player_id) from {{ ref('int_player_affiliate_attribution') }}) as attr_total
)
where agg_total != attr_total
