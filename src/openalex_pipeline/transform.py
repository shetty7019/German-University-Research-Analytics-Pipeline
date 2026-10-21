"""Convert OpenAlex's nested work objects into stable database rows."""

from __future__ import annotations

from typing import Any

from openalex_pipeline.openalex import short_id


def transform_work(work: dict[str, Any], institution_id: str) -> dict[str, Any]:
    topic = work.get("primary_topic") or {}
    open_access = work.get("open_access") or {}
    authorships = work.get("authorships") or []
    institutions: set[str] = set()
    for authorship in authorships:
        for institution in authorship.get("institutions") or []:
            institution_key = short_id(institution.get("id"))
            if institution_key:
                institutions.add(institution_key)

    return {
        "work_id": short_id(work.get("id")),
        "doi": work.get("doi"),
        "title": work.get("title"),
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "work_type": work.get("type"),
        "language": work.get("language"),
        "cited_by_count": work.get("cited_by_count") or 0,
        "is_retracted": bool(work.get("is_retracted", False)),
        "is_open_access": bool(open_access.get("is_oa", False)),
        "oa_status": open_access.get("oa_status"),
        "topic_id": short_id(topic.get("id")),
        "topic_name": topic.get("display_name"),
        "topic_subfield": (topic.get("subfield") or {}).get("display_name"),
        "institution_id": institution_id,
        "collaborating_institutions": sorted(institutions),
        "fwci": work.get("fwci"),
        "updated_date": work.get("updated_date"),
        "raw": work,
    }


def transform_page(payload: dict[str, Any], institution_id: str) -> list[dict[str, Any]]:
    return [transform_work(work, institution_id) for work in payload.get("results", [])]