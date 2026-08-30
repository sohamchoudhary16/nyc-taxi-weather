PY := python
export PYTHONPATH := src
export DBT_PROFILES_DIR := dbt

.PHONY: help setup ingest load build test lint analysis all clean databricks

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$2}'

setup:   ## create venv deps + dbt packages
	$(PY) -m pip install -r requirements.txt
	cd dbt && dbt deps

ingest:  ## download TLC trips + Open-Meteo weather into data/raw
	$(PY) -m taxi.ingest_trips
	$(PY) -m taxi.ingest_weather

load:    ## register raw files as bronze tables in DuckDB
	$(PY) -m taxi.load_duckdb

build:   ## run all dbt models
	cd dbt && dbt build --target dev

test:    ## unit tests + dbt tests
	$(PY) -m pytest tests -q
	cd dbt && dbt test --target dev

lint:
	ruff check src tests

analysis: ## produce the charts in docs/figures
	$(PY) -m taxi.analysis

all: ingest load build test analysis  ## end to end, ~5 minutes from cold

databricks: ## run the identical models against Databricks Free Edition
	cd dbt && dbt build --target databricks

clean:
	rm -rf data/warehouse.duckdb dbt/target dbt/dbt_packages
