.PHONY: help install install-all sync lint format typecheck test test-live cov \
        validate prewarm refresh-hints refresh-facets vacuum-plans \
        diff-versions metrics audit \
        run docker-build docker-run clean

PYTHON_VERSION ?= 3.11
IMAGE ?= cxg-census-mcp
TAG   ?= dev

help:  ## Show this help
	@awk 'BEGIN{FS=":.*##"; printf "\nUsage: make <target>\n\nTargets:\n"} \
	     /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## --- Setup -----------------------------------------------------------------

install:  ## uv sync with dev extras (no live Census)
	uv sync --extra dev

install-all:  ## uv sync with dev + cellxgene_census extras
	uv sync --extra dev --extra census

sync: install  ## Alias for install

## --- Static checks ---------------------------------------------------------

lint:  ## Run ruff check
	uv run ruff check .

format:  ## Run ruff format
	uv run ruff format .

typecheck:  ## Run mypy on src
	uv run mypy src/cxg_census_mcp

audit:  ## Scan installed deps for known CVEs
	uv run --with pip-audit pip-audit --strict --skip-editable

## --- Tests -----------------------------------------------------------------

test:  ## Run unit + integration tests in mock mode
	CXG_CENSUS_MCP_MOCK_MODE=1 uv run pytest -m "not live"

test-live:  ## Run tests that hit real OLS / Census (slow, network)
	uv run pytest -m live

cov:  ## Run tests with coverage report
	CXG_CENSUS_MCP_MOCK_MODE=1 uv run pytest -m "not live" \
		--cov --cov-report=term-missing --cov-report=html --cov-fail-under=70

validate:  ## Validate data files and test fixtures
	uv run python scripts/validate_fixtures.py

## --- Operational tasks -----------------------------------------------------

prewarm:  ## Prewarm OLS cache from data/ols_seed_terms.json
	uv run python scripts/prewarm_ols_cache.py --with-dag

refresh-hints:  ## Refresh data/ontology_hints.json from OLS
	uv run python scripts/refresh_ontology_hints.py

refresh-facets:  ## Refresh data/facet_catalog.json from the live Census
	uv run python scripts/refresh_facet_catalog.py

vacuum-plans:  ## Drop expired plan-cache entries
	uv run python -c "from cxg_census_mcp.planner.plan_store import get_plan_store; \
	import json; ps = get_plan_store(); print(json.dumps({'reclaimed': ps.vacuum(), 'stats': ps.stats()}))"

diff-versions:  ## Diff two Census schema versions (FROM=2024-07-01 TO=stable)
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ]; then \
		echo "usage: make diff-versions FROM=<old> TO=<new>"; exit 2; \
	fi
	uv run python scripts/diff_schema_versions.py --from $(FROM) --to $(TO)

metrics:  ## Dump runtime metrics (cache stats, plan-store stats) as Prometheus textfile
	uv run python -m cxg_census_mcp.metrics_dump > metrics.prom
	@echo "Wrote metrics.prom"

## --- Run -------------------------------------------------------------------

run:  ## Run server over stdio
	uv run cxg-census-mcp

## --- Docker ----------------------------------------------------------------

docker-build:  ## Build the docker image
	docker build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) -t $(IMAGE):$(TAG) .

docker-run:  ## Run the docker image (stdio)
	docker run --rm -i \
		-e CXG_CENSUS_MCP_MOCK_MODE=$${CXG_CENSUS_MCP_MOCK_MODE:-0} \
		-e CXG_CENSUS_MCP_CENSUS_VERSION=$${CXG_CENSUS_MCP_CENSUS_VERSION:-stable} \
		$(IMAGE):$(TAG)

## --- Misc ------------------------------------------------------------------

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
