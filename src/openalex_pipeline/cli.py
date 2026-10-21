"""Command-line entry point for one institution/date-window extraction."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

from openalex_pipeline.openalex import OpenAlexClient
from openalex_pipeline.storage import (
    archive_page,
    create_s3_client,
    ensure_bucket,
    load_works,
)
from openalex_pipeline.transform import transform_page

LOGGER = logging.getLogger("openalex_pipeline")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load OpenAlex works for one institution.")
    parser.add_argument("--ror", default=os.getenv("OPENALEX_ROR", "https://ror.org/058kzsd48"))
    parser.add_argument("--start", default=os.getenv("START_DATE", "2025-01-01"))
    parser.add_argument("--end", default=os.getenv("END_DATE", date.today().isoformat()))
    parser.add_argument("--max-works", type=int, default=int(os.getenv("MAX_WORKS", "0")))
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET", "openalex-lake"))
    return parser


def run(args: argparse.Namespace) -> int:
    if not args.database_url:
        raise ValueError("DATABASE_URL is required (set it in the environment or pass --database-url)")
    date.fromisoformat(args.start)
    date.fromisoformat(args.end)
    if args.start > args.end:
        raise ValueError("--start must be on or before --end")

    api = OpenAlexClient()
    institution = api.resolve_institution(args.ror)
    institution_id = institution["institution_id"]
    if not institution_id:
        raise ValueError(f"Could not resolve institution ROR: {args.ror}")
    LOGGER.info("Resolved %s to %s (%s)", args.ror, institution["name"], institution_id)

    s3 = create_s3_client()
    ensure_bucket(s3, args.bucket)
    total_loaded = 0
    for page_number, payload in api.iter_work_pages(
        institution_id,
        args.start,
        args.end,
        per_page=args.per_page,
        max_works=args.max_works,
    ):
        key = archive_page(s3, args.bucket, institution_id, args.start, args.end, page_number, payload)
        rows = transform_page(payload, institution_id)
        loaded = load_works(args.database_url, rows)
        total_loaded += loaded
        LOGGER.info(
            "Page %d: %d works loaded; API total=%s; raw=s3://%s/%s",
            page_number,
            loaded,
            payload.get("meta", {}).get("count", "unknown"),
            args.bucket,
            key,
        )
    LOGGER.info("Finished. Processed %d works for %s.", total_loaded, institution["name"])
    return 0


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    try:
        exit_code = run(build_parser().parse_args())
    except (ValueError, OSError, RuntimeError) as exc:
        LOGGER.error("Pipeline failed: %s", exc)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()