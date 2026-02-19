.PHONY: help venv install activate venv-guard lint lint-tests format format-tests
SOURCES := run.py apps coded_tools plugins
TESTS   := tests
.DEFAULT_GOAL := help

RUFF_FORMAT_CHECK := --check --diff
RUFF_LINT_CHECK := --output-format=full
RUFF_IMPORTS_FIX := --select I --fix

venv: # Set up a virtual environment in project
	@if [ ! -d "venv" ]; then \
		echo "Creating virtual environment in ./venv..."; \
		python3 -m venv venv; \
		echo "Virtual environment created."; \
	else \
		echo "Virtual environment already exists."; \
	fi

venv-guard: 
	@if [ -z "$$VIRTUAL_ENV" ] && [ -z "$$CONDA_DEFAULT_ENV" ] && \
	  ! (pipenv --venv >/dev/null 2>&1) && ! (uv venv list >/dev/null 2>&1); then \
		echo ""; \
		echo "Error: This task must be run inside an active Python virtual environment."; \
		echo "Detected: no venv, virtualenv, Poetry, Pipenv, Conda, or uv environment."; \
		echo "Please activate one of the supported environments before continuing."; \
		echo ""; \
		echo "Examples:"; \
		echo "  venv:       source venv/bin/activate"; \
		echo "  Poetry:     poetry shell"; \
		echo "  Pipenv:     pipenv shell"; \
		echo "  Conda:      conda activate <env_name>"; \
		echo "  uv:         source .venv/bin/activate"; \
		echo ""; \
		exit 1; \
	fi

install: venv ## Install all dependencies in the virtual environment
	@echo "Installing all dependencies including test dependencies in virtual environment..."
	@. venv/bin/activate && pip install --upgrade pip
	@. venv/bin/activate && pip install -r requirements.txt -r requirements-build.txt
	@echo "All dependencies including test dependencies installed successfully."

activate: ## Activate the venv
	@if [ ! -d "venv" ]; then \
		echo "No virtual environment detected..."; \
		echo "To create a virtual environment and install dependencies, run:"; \
		echo "    make install"; \
		echo ""; \
	else \
		echo "To activate the environment in your current shell, run:"; \
		echo "    source venv/bin/activate"; \
		echo ""; \
	fi

format-source: venv-guard
	# Apply format and import sorting via ruff
	ruff check $(RUFF_IMPORTS_FIX) $(SOURCES)
	ruff format $(SOURCES)

format-tests: venv-guard
	# Apply format and import sorting via ruff
	ruff check $(RUFF_IMPORTS_FIX) $(TESTS)
	ruff format $(TESTS)

format: format-source format-tests

lint-check-source: venv-guard
	# Run format and lint checks via ruff, then pylint
	ruff format $(SOURCES) $(RUFF_FORMAT_CHECK)
	ruff check $(SOURCES) $(RUFF_LINT_CHECK)
	pylint $(SOURCES)/
	pymarkdown --config ./.pymarkdownlint.yaml scan ./docs ./README.md

lint-check-tests: venv-guard
	# Run format and lint checks via ruff, then pylint
	ruff format $(TESTS) $(RUFF_FORMAT_CHECK)
	ruff check $(TESTS) $(RUFF_LINT_CHECK)
	pylint $(TESTS)

lint-check: lint-check-source lint-check-tests

lint: format lint-check

test: lint ## Run tests with coverage
	python -m pytest tests/ -v --cov=coded_tools,run.py -m "not integration"

test-integration: install
	@. venv/bin/activate && \
	export PYTHONPATH=`pwd` && \
	export AGENT_TOOL_PATH=coded_tools/ && \
	export AGENT_MANIFEST_FILE=registries/manifest.hocon && \
	export AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5 && \
	pytest -s -m "integration" --timer-top-n 100

help: ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[m %s\n", $$1, $$2}'
