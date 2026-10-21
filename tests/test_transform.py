from openalex_pipeline.transform import transform_page, transform_work


def test_transform_work_flattens_nested_fields_and_keeps_raw_record():
    work = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1234/example",
        "title": "A research paper",
        "publication_year": 2025,
        "publication_date": "2025-03-14",
        "type": "article",
        "cited_by_count": 4,
        "open_access": {"is_oa": True, "oa_status": "gold"},
        "primary_topic": {
            "id": "https://openalex.org/T2",
            "display_name": "Data engineering",
            "subfield": {"display_name": "Information Systems"},
        },
        "authorships": [
            {"institutions": [{"id": "https://openalex.org/I2"}, {"id": "I1"}]},
            {"institutions": [{"id": "https://openalex.org/I2"}]},
        ],
    }

    row = transform_work(work, "I1")

    assert row["work_id"] == "W1"
    assert row["is_open_access"] is True
    assert row["topic_name"] == "Data engineering"
    assert row["collaborating_institutions"] == ["I1", "I2"]
    assert row["raw"] == work


def test_transform_page_handles_missing_results():
    assert transform_page({}, "I1") == []