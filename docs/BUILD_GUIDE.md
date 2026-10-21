# Build and Push Guide

Follow these steps from the repository root. The project files contain the complete implementation; this guide gives the order to assemble, test, run, and publish it. Commit one logical step at a time so the GitHub history shows how the pipeline was built.

## 1. Prepare the repository

Check the current branch and files before changing anything:

```sh
git status --short --branch
git pull --ff-only origin main
```

Create a feature branch if you are not already using one:

```sh
git switch -c build-openalex-pipeline
```

Keep `.env` private. The committed `.env.example` contains only local defaults and an empty API key.

## 2. Build the Python package and API client

Review `pyproject.toml`, `requirements.txt`, and `src/openalex_pipeline/openalex.py`. The client resolves a ROR ID, selects only required work fields, retries transient GET failures, throttles calls, and follows `meta.next_cursor`.

Install and test:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest tests/test_openalex.py
```

Commit:

```sh
git add pyproject.toml requirements.txt src/openalex_pipeline/openalex.py src/openalex_pipeline/__init__.py tests/test_openalex.py
git commit -m "Add OpenAlex client with cursor pagination"
```

## 3. Normalize work records

Read `src/openalex_pipeline/transform.py` and `tests/test_transform.py`. The transform extracts topics, access status, authorship institution IDs, and core citation fields while retaining the original record for auditability.

Check and commit:

```sh
pytest tests/test_transform.py
git add src/openalex_pipeline/transform.py tests/test_transform.py
git commit -m "Normalize nested OpenAlex work records"
```

## 4. Add S3 and Postgres persistence

Read `src/openalex_pipeline/storage.py`. Raw pages are stored in timestamped S3 keys; the Postgres `works` table uses `work_id` as its primary key and an upsert for safe reruns.

Start the local dependencies and check connectivity:

```sh
cp .env.example .env
docker compose up -d postgres s3
python scripts/smoke_check.py
```

Commit:

```sh
git add src/openalex_pipeline/storage.py scripts/smoke_check.py
git commit -m "Persist raw pages to S3 and works to Postgres"
```

## 5. Connect the pipeline CLI

Read `src/openalex_pipeline/cli.py`. Configure `.env` with a date window and optional API key. Use a small limit first:

```sh
MAX_WORKS=200 docker compose run --rm pipeline
```

The cap stops at a page boundary. Re-running may re-fetch the window but does not duplicate rows.

Commit:

```sh
git add src/openalex_pipeline/cli.py
git commit -m "Add configurable OpenAlex pipeline command"
```

## 6. Build analytics with dbt

Inspect `dbt/models/staging` and `dbt/models/marts`. Build and test after the pipeline has loaded at least one page:

```sh
docker compose run --rm --no-deps dbt
```

Confirm the `analytics` schema contains the annual institution, topic, and collaboration marts.

Commit:

```sh
git add dbt
git commit -m "Add dbt research output models and tests"
```

## 7. Run the whole stack

```sh
docker compose build
docker compose up --abort-on-container-exit pipeline dbt
docker compose ps -a
```

To reset all local database and S3 state, this is destructive:

```sh
docker compose down -v
```

Use it only when you intentionally want a clean local run.

## 8. Verify CI and publish

Run local checks before pushing:

```sh
pytest
ruff check src tests scripts
```

Push the branch and open a pull request:

```sh
git push -u origin build-openalex-pipeline
```

After CI passes, merge the pull request or push directly to `main` according to your repository workflow. Check that the GitHub Actions run is green and the README architecture diagram renders. Do not include `.env`, AWS credentials, or API keys in the commit.