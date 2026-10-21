"""Smoke check: can we reach Postgres and S3?"""
import os

import boto3
import psycopg
from botocore.client import Config

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pipeline:pipeline@localhost:5432/openalex")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None   # None means real AWS S3
S3_BUCKET = os.getenv("S3_BUCKET", "openalex-lake")
REGION = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")


def check_postgres():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1")
            print(cur.fetchone())


def check_s3():
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        region_name=REGION,
        config=Config(s3={"addressing_style": "path"}),
    )
    create_bucket_args = {"Bucket": S3_BUCKET}
    if not S3_ENDPOINT_URL and REGION != "us-east-1":
        create_bucket_args["CreateBucketConfiguration"] = {"LocationConstraint": REGION}
    s3.create_bucket(**create_bucket_args)
    s3.put_object(Bucket=S3_BUCKET, Key="hello.txt", Body=b"hello")
    for obj in s3.list_objects_v2(Bucket=S3_BUCKET).get("Contents", []):
        print(obj["Key"])


if __name__ == "__main__":
    check_postgres()
    check_s3()
    print("All good")
