.PHONY: install test lint up run dbt down clean

install:
	python -m pip install -e '.[dev]'

test:
	python -m pytest

lint:
	ruff check src tests scripts

up:
	docker compose up -d postgres s3

run:
	docker compose run --rm pipeline

dbt:
	docker compose run --rm dbt

down:
	docker compose down

clean:
	docker compose down -v