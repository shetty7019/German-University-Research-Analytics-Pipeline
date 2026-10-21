"""Smoke check: can we reach Postgres and S3?"""
import os

import psycopg

from openalex_pipeline.storage import create_s3_client, ensure_bucket

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pipeline:pipeline@localhost:5432/openalex")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None   # None means real AWS S3
S3_BUCKET = os.getenv("S3_BUCKET", "openalex-lake")


def check_postgres():
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("select 1")
        print(cur.fetchone())


def check_s3():
    s3 = create_s3_client()
    ensure_bucket(s3, S3_BUCKET)
    s3.put_object(Bucket=S3_BUCKET, Key="hello.txt", Body=b"hello")
    for obj in s3.list_objects_v2(Bucket=S3_BUCKET).get("Contents", []):
        print(obj["Key"])


if __name__ == "__main__":
    check_postgres()
    check_s3()
    print("All good")
