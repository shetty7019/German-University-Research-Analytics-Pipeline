# OpenAlex Research Output Pipeline

An end-to-end data engineering project that extracts scholarly works for an institution from the public OpenAlex API, archives source pages in S3-compatible object storage, loads an idempotent Postgres table, and builds research-output analytics with dbt.

The default institution is the University of Paderborn (`https://ror.org/058kzsd48`). 

## Architecture

```mermaid
flowchart LR
    OA[OpenAlex API<br/>ROR lookup + cursor pages] --> ETL[Python pipeline<br/>request, flatten, validate]
    ETL -->|Raw JSON pages| S3[(S3-compatible lake<br/>SeaweedFS locally / AWS S3)]
    ETL -->|Idempotent upsert| PG[(PostgreSQL<br/>works table)]
    PG --> DBT[dbt staging models]
    DBT --> MARTS[(Analytics schema<br/>institution year, topics, collaboration)]
    TESTS[pytest + dbt tests + CI] -. validates .-> ETL
    TESTS -. validates .-> DBT
```

See [the standalone architecture diagram](docs/architecture.mmd) and [the build guide](docs/BUILD_GUIDE.md) for setup, validation, and push steps.

## Quick start

Prerequisites: Docker Desktop with Compose v2, Git, and an OpenAlex API key if your usage requires one. The API key is optional for a small run and must never be committed.

```sh
cp .env.example .env
# Edit .env and set OPENALEX_API_KEY if you have one.
docker compose up -d postgres s3
docker compose run --rm pipeline
docker compose run --rm --no-deps dbt
```

The ETL service exits after loading its configured date window. The dbt service builds views/tables in the Postgres `analytics` schema and runs data tests. Run them in sequence as shown; `--no-deps` on dbt prevents Compose from triggering another ETL run.

To stop the services but keep local data, run `docker compose down`. To delete the local database and object-store volumes, run `docker compose down -v`.

## Local development

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
```

The tests stub the HTTP calls and do not need OpenAlex, Postgres, or S3. For the integrated Docker run, configure `.env` first. `scripts/smoke_check.py` verifies connectivity to Postgres and S3; when running it from the host against Compose, export `DATABASE_URL=postgresql://pipeline:pipeline@localhost:5432/openalex`, `S3_ENDPOINT_URL=http://localhost:8333`, `AWS_ACCESS_KEY_ID=lake-admin`, and `AWS_SECRET_ACCESS_KEY=lake-secret-key` first.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENALEX_API_KEY` | empty | Optional OpenAlex credential |
| `OPENALEX_ROR` | Paderborn ROR | Institution to extract |
| `START_DATE` | `2025-01-01` | Inclusive publication date lower bound |
| `END_DATE` | `2025-12-31` | Inclusive publication date upper bound |
| `MAX_WORKS` | `0` | Maximum rows to fetch; `0` means all results |
| `DATABASE_URL` | local Postgres URL | Postgres connection string |
| `S3_ENDPOINT_URL` | local SeaweedFS URL | Set empty to use AWS S3 |
| `S3_BUCKET` | `openalex-lake` | Raw JSON bucket |

Use a smaller cap for a quick first run, for example `MAX_WORKS=200`. The setting counts at page boundaries, so it can process up to one page beyond the requested cap. For local Compose, the service uses container DNS. To use AWS, set `S3_ENDPOINT_URL=` in `.env`, provide AWS credentials through `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or the SDK credential chain), and ensure the bucket exists or the IAM role can create it.

## Data products

- `works`: flattened work records with the source JSON retained in a JSONB field. The OpenAlex work ID is the primary key and conflict updates make repeat runs idempotent.
- S3 `raw/`: timestamped API response pages partitioned by institution and requested date window.
- `analytics.mart_institution_year`: annual work count, OA share, citation totals/average, and retracted work count.
- `analytics.mart_topic_output`: annual publication and citation metrics by OpenAlex topic.
- `analytics.mart_collaboration`: institution collaboration pairs per year.

OpenAlex is an external public API. Its availability, rate limits, schema, and terms are outside this project’s control. This project logs no API key and redacts credentials from HTTP exception text. Avoid putting secrets in command-line arguments, screenshots, issue reports, or committed files.

## Repository map

- `src/openalex_pipeline/openalex.py`: ROR lookup, limited-field selection, retries, throttling, and cursor iteration.
- `src/openalex_pipeline/transform.py`: nested API response normalization.
- `src/openalex_pipeline/storage.py`: S3-compatible raw archive and Postgres upsert.
- `src/openalex_pipeline/cli.py`: pipeline command.
- `dbt/models`: source tests, staging, and analytics marts.
- `tests`: isolated tests that require no network access.
- `.github/workflows/ci.yml`: lint, unit tests, and dbt parse check.

## Scope and next steps

This is a portfolio-scale batch pipeline. It currently re-reads a requested date window; the upsert keeps the warehouse correct, while raw page objects are intentionally retained as an audit trail. A production deployment should add a durable extraction watermark, structured metrics/alerting, secret-manager integration, and a scheduler (for example, Airflow or Dagster).