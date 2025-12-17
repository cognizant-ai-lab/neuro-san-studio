.PHONY: help venv install activate venv-guard lint lint-tests format format-tests
SOURCES := run.py apps coded_tools
TESTS   := tests
.DEFAULT_GOAL := help

ISORT_FLAGS := --force-single-line
ISORT_CHECK := --check-only --diff
BLACK_CHECK := --check --diff

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
	# Apply format changes from isort and black
	isort $(SOURCES) $(ISORT_FLAGS)
	black $(SOURCES)

format-tests: venv-guard
	# Apply format changes from isort and black
	isort $(TESTS) $(ISORT_FLAGS)
	black $(TESTS)

format: format-source format-tests

lint-check-source: venv-guard
	# Run format checks and fail if isort or black need changes
	isort $(SOURCES) $(ISORT_FLAGS) $(ISORT_CHECK)
	black $(SOURCES) $(BLACK_CHECK)
	flake8 $(SOURCES)
	pylint $(SOURCES)/
	pymarkdown --config ./.pymarkdownlint.yaml scan ./docs ./README.md

lint-check-tests: venv-guard
	# Run format checks and fail if isort or black need changes
	isort $(TESTS) $(ISORT_FLAGS) $(ISORT_CHECK)
	black $(TESTS) $(BLACK_CHECK)
	flake8 $(TESTS)
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
	pytest -s -m "integration" --timer-top-n 100

help: ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[m %s\n", $$1, $$2}'
