select
    institution_id,
    publication_year,
    topic_id,
    topic_name,
    topic_subfield,
    count(*) as works_count,
    sum(cited_by_count) as citations_total,
    round(avg(fwci)::numeric, 3) as fwci_avg
from {{ ref('stg_works') }}
where topic_id is not null
group by institution_id, publication_year, topic_id, topic_name, topic_subfield