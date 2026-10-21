select
    institution_id,
    publication_year,
    count(*) as works_count,
    count(*) filter (where is_open_access) as open_access_works,
    round(
        count(*) filter (where is_open_access)::numeric / nullif(count(*), 0),
        4
    ) as open_access_share,
    sum(cited_by_count) as citations_total,
    round(avg(cited_by_count)::numeric, 2) as citations_per_work_avg,
    count(*) filter (where is_retracted) as retracted_works
from {{ ref('stg_works') }}
where publication_year is not null
group by institution_id, publication_year