"""S3-compatible raw-page archive and idempotent Postgres warehouse loader."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
import psycopg
from botocore.client import Config
from botocore.exceptions import ClientError
from psycopg.types.json import Jsonb

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS works (
    work_id TEXT PRIMARY KEY,
    doi TEXT,
    title TEXT,
    publication_year INTEGER,
    publication_date DATE,
    work_type TEXT,
    language TEXT,
    cited_by_count INTEGER NOT NULL DEFAULT 0,
    is_retracted BOOLEAN NOT NULL DEFAULT FALSE,
    is_open_access BOOLEAN NOT NULL DEFAULT FALSE,
    oa_status TEXT,
    topic_id TEXT,
    topic_name TEXT,
    topic_subfield TEXT,
    institution_id TEXT NOT NULL,
    collaborating_institutions JSONB NOT NULL DEFAULT '[]'::jsonb,
    fwci DOUBLE PRECISION,
    updated_date DATE,
    raw JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

UPSERT_SQL = """
INSERT INTO works (
    work_id, doi, title, publication_year, publication_date, work_type, language,
    cited_by_count, is_retracted, is_open_access, oa_status, topic_id, topic_name,
    topic_subfield, institution_id, collaborating_institutions, fwci, updated_date, raw, loaded_at
) VALUES (
    %(work_id)s, %(doi)s, %(title)s, %(publication_year)s, %(publication_date)s,
    %(work_type)s, %(language)s, %(cited_by_count)s, %(is_retracted)s, %(is_open_access)s,
    %(oa_status)s, %(topic_id)s, %(topic_name)s, %(topic_subfield)s, %(institution_id)s,
    %(collaborating_institutions)s, %(fwci)s, %(updated_date)s, %(raw)s, %(loaded_at)s
)
ON CONFLICT (work_id) DO UPDATE SET
    doi = EXCLUDED.doi,
    title = EXCLUDED.title,
    publication_year = EXCLUDED.publication_year,
    publication_date = EXCLUDED.publication_date,
    work_type = EXCLUDED.work_type,
    language = EXCLUDED.language,
    cited_by_count = EXCLUDED.cited_by_count,
    is_retracted = EXCLUDED.is_retracted,
    is_open_access = EXCLUDED.is_open_access,
    oa_status = EXCLUDED.oa_status,
    topic_id = EXCLUDED.topic_id,
    topic_name = EXCLUDED.topic_name,
    topic_subfield = EXCLUDED.topic_subfield,
    institution_id = EXCLUDED.institution_id,
    collaborating_institutions = EXCLUDED.collaborating_institutions,
    fwci = EXCLUDED.fwci,
    updated_date = EXCLUDED.updated_date,
    raw = EXCLUDED.raw,
    loaded_at = EXCLUDED.loaded_at
"""


def create_s3_client():
    endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"),
        config=Config(s3={"addressing_style": "path"}),
    )


def ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        error_code = exc.response.get("Error", {}).get("Code")
        if status_code != 404 and error_code not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        args: dict[str, Any] = {"Bucket": bucket}
        if not os.getenv("S3_ENDPOINT_URL") and os.getenv("AWS_DEFAULT_REGION", "eu-central-1") != "us-east-1":
            args["CreateBucketConfiguration"] = {
                "LocationConstraint": os.getenv("AWS_DEFAULT_REGION", "eu-central-1")
            }
        client.create_bucket(**args)


def archive_page(client, bucket: str, institution_id: str, start: str, end: str,
                 page_number: int, payload: dict[str, Any]) -> str:
    fetched_at = datetime.now(timezone.utc)
    key = (
        f"raw/institution={institution_id}/start={start}/end={end}/"
        f"page-{page_number:05d}-{fetched_at.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    return key


def load_works(database_url: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    parameters = []
    for row in rows:
        item = dict(row)
        item["collaborating_institutions"] = Jsonb(item["collaborating_institutions"])
        item["raw"] = Jsonb(item["raw"])
        item["loaded_at"] = now
        parameters.append(item)
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(CREATE_TABLE_SQL)
        cursor.executemany(UPSERT_SQL, parameters)
    return len(rows)