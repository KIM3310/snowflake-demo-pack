# snowflake-demo-pack — Makefile
# Production-quality Snowflake industry demo library
# Author: Doeon Kim

SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
PIP ?= pip3
VENV ?= .venv
ACTIVATE = source $(VENV)/bin/activate

# Dry-run by default: no real Snowflake connection needed for CI/scaffolding
export SNOWFLAKE_DEMO_DRY_RUN ?= 1

.PHONY: help
help:
	@echo "snowflake-demo-pack"
	@echo ""
	@echo "Setup targets:"
	@echo "  make setup                   Create virtualenv and install deps"
	@echo "  make snowflake-setup         Provision database and warehouse"
	@echo "  make teardown                Drop all demo objects from Snowflake"
	@echo ""
	@echo "Per-industry demos (run in isolated schemas):"
	@echo "  make demo-finance            Run finance fraud detection demo"
	@echo "  make demo-retail             Run retail customer 360 demo"
	@echo "  make demo-manufacturing      Run manufacturing predictive maintenance demo"
	@echo "  make demo-healthcare         Run healthcare EHR governed analytics demo"
	@echo "  make demo-media              Run media content recommendation demo"
	@echo "  make demo-all                Run all five demos sequentially"
	@echo ""
	@echo "Quality targets:"
	@echo "  make lint                    Run sqlfluff + ruff"
	@echo "  make format                  Apply black and sqlfluff fix"
	@echo "  make check                   Compile-check all Python files"
	@echo ""
	@echo "Run with SNOWFLAKE_DEMO_DRY_RUN=0 to execute against a real account."

.PHONY: setup
setup:
	@echo "Creating virtual environment at $(VENV)..."
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(ACTIVATE) && $(PIP) install --upgrade pip
	@$(ACTIVATE) && $(PIP) install -e ".[dev]"
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"

.PHONY: snowflake-setup
snowflake-setup:
	@echo "Provisioning SNOWFLAKE_DEMO_PACK database and warehouse..."
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('common/setup.sql')"

.PHONY: teardown
teardown:
	@echo "Dropping all demo objects..."
	@bash scripts/teardown.sh

.PHONY: demo-finance
demo-finance:
	@echo "===> Finance: Fraud Detection"
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/01-finance-fraud-detection/01-setup.sql')"
	@$(ACTIVATE) && $(PYTHON) demos/01-finance-fraud-detection/02-load-data.py
	@$(ACTIVATE) && $(PYTHON) demos/01-finance-fraud-detection/03-fraud-model.py
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/01-finance-fraud-detection/04-analytics.sql')"

.PHONY: demo-retail
demo-retail:
	@echo "===> Retail: Customer 360"
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/02-retail-customer-360/01-setup.sql')"
	@$(ACTIVATE) && $(PYTHON) demos/02-retail-customer-360/02-load-data.py
	@$(ACTIVATE) && $(PYTHON) demos/02-retail-customer-360/03-fraud-model.py
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/02-retail-customer-360/04-analytics.sql')"

.PHONY: demo-manufacturing
demo-manufacturing:
	@echo "===> Manufacturing: Predictive Maintenance"
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/03-manufacturing-predictive-maintenance/01-setup.sql')"
	@$(ACTIVATE) && $(PYTHON) demos/03-manufacturing-predictive-maintenance/02-load-data.py
	@$(ACTIVATE) && $(PYTHON) demos/03-manufacturing-predictive-maintenance/03-fraud-model.py
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/03-manufacturing-predictive-maintenance/04-analytics.sql')"

.PHONY: demo-healthcare
demo-healthcare:
	@echo "===> Healthcare: Governed Analytics"
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/04-healthcare-ehr-governed-analytics/01-setup.sql')"
	@$(ACTIVATE) && $(PYTHON) demos/04-healthcare-ehr-governed-analytics/02-load-data.py
	@$(ACTIVATE) && $(PYTHON) demos/04-healthcare-ehr-governed-analytics/03-fraud-model.py
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/04-healthcare-ehr-governed-analytics/04-analytics.sql')"

.PHONY: demo-media
demo-media:
	@echo "===> Media: Content Recommendation"
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/05-media-content-recommendation/01-setup.sql')"
	@$(ACTIVATE) && $(PYTHON) demos/05-media-content-recommendation/02-load-data.py
	@$(ACTIVATE) && $(PYTHON) demos/05-media-content-recommendation/03-fraud-model.py
	@$(ACTIVATE) && $(PYTHON) -c "from common.connection import run_sql_file; run_sql_file('demos/05-media-content-recommendation/04-analytics.sql')"

.PHONY: demo-all
demo-all: demo-finance demo-retail demo-manufacturing demo-healthcare demo-media
	@echo "All 5 demos completed."

.PHONY: lint
lint:
	@$(ACTIVATE) && sqlfluff lint common/ demos/ --dialect snowflake || true
	@$(ACTIVATE) && ruff check common/ demos/ || true

.PHONY: format
format:
	@$(ACTIVATE) && black common/ demos/
	@$(ACTIVATE) && sqlfluff fix common/ demos/ --dialect snowflake || true

.PHONY: check
check:
	@echo "Compile-checking all Python modules..."
	@find common demos -name "*.py" -type f -exec $(PYTHON) -m py_compile {} \;
	@echo "All Python files syntactically valid."

.PHONY: clean
clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build dist .coverage htmlcov
	@echo "Clean complete."
