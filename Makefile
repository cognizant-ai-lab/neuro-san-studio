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
	@if [ -z "$$VIRTUAL_ENV" ]; then \
	  echo ""; \
	  echo "Error: this task must run inside a Python virtual environment."; \
	  echo "Activate it, e.g.  source venv/bin/activate"; \
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
	pymakthon -m pytest tests/ -v --cov=coded_tools,run.py -m "not integration"

test-integration: install
	@. venv/bin/activate && pytest -s -m "integration"

help: ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[m %s\n", $$1, $$2}'
