with expanded as (
    select
        w.work_id,
        w.institution_id,
        collaborator.value #>> '{}' as collaborator_id,
        w.publication_year,
        w.cited_by_count
    from {{ ref('stg_works') }} as w
    cross join lateral jsonb_array_elements(w.collaborating_institutions) as collaborator(value)
)
select
    institution_id,
    collaborator_id,
    publication_year,
    count(distinct work_id) as shared_works_count,
    sum(cited_by_count) as citations_total
from expanded
where collaborator_id <> institution_id
group by institution_id, collaborator_id, publication_year