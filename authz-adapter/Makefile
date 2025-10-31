.PHONY: help install test test-coverage clean

PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python

help:
	@echo 'Available commands:'
	@echo '  install       Install dependencies'
	@echo '  test          Run all tests'
	@echo '  test-coverage Run tests with coverage'
	@echo '  clean         Clean up test artifacts'

install:
	@test -d $(VENV_DIR) || $(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements.txt
	$(VENV_PY) -m pip install -r requirements-dev.txt

# Run all tests by default
test: test-coverage

# Run only unit tests
test-unit: install
	$(VENV_PY) -m pytest tests/ -v -k "not Docker" --ignore=tests/test_integration.py

# Run unit and integration tests
test-integration: install
	$(VENV_PY) -m pytest tests/ -v -k "not Docker"

# Run tests with coverage (excludes Docker tests)
test-coverage: install
	$(VENV_PY) -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html -k "not Docker"

clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf __pycache__/
	rm -rf tests/__pycache__/
	rm -f .coverage
	find . -name "*.pyc" -delete
