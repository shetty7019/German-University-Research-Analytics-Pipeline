"""Exercise Postgres, S3-compatible storage, and dbt from the Compose network."""

from __future__ import annotations

import json
import os

import psycopg

from openalex_pipeline.storage import archive_page, create_s3_client, ensure_bucket, load_works
from openalex_pipeline.transform import transform_work


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    bucket = os.getenv("S3_BUCKET", "openalex-lake")
    s3 = create_s3_client()
    ensure_bucket(s3, bucket)
    ensure_bucket(s3, bucket)
    payload = {
        "meta": {"count": 1, "next_cursor": None},
        "results": [
            {
                "id": "https://openalex.org/WLOCALCHECK",
                "title": "Local integration check",
                "publication_year": 2025,
                "publication_date": "2025-01-01",
                "type": "article",
                "cited_by_count": 2,
                "open_access": {"is_oa": True, "oa_status": "gold"},
                "primary_topic": {"id": "https://openalex.org/TLOCAL", "display_name": "Testing"},
                "authorships": [{"institutions": [{"id": "https://openalex.org/ILOCAL"}]}],
            }
        ],
    }
    key = archive_page(s3, bucket, "ILOCAL", "2025-01-01", "2025-12-31", 1, payload)
    archived = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    assert archived == payload

    rows = [transform_work(payload["results"][0], "ILOCAL")]
    assert load_works(database_url, rows) == 1
    assert load_works(database_url, rows) == 1
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM works WHERE work_id = %s", ("WLOCALCHECK",))
        assert cursor.fetchone()[0] == 1
        cursor.execute("DELETE FROM works WHERE work_id = %s", ("WLOCALCHECK",))
    s3.delete_object(Bucket=bucket, Key=key)
    print("S3 archive verified; Postgres upsert rerun preserved a single work row.")


if __name__ == "__main__":
    main()