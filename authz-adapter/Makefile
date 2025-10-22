.PHONY: help install test test-coverage clean

PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest

help:
	@echo 'Available commands:'
	@echo '  install       Install dependencies'
	@echo '  test          Run all tests'
	@echo '  test-coverage Run tests with coverage'
	@echo '  clean         Clean up test artifacts'

install:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

test:
	$(PYTEST) tests/ -v

test-coverage:
	$(PYTEST) tests/ -v --cov=app --cov-report=term-missing --cov-report=html

clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf __pycache__/
	rm -rf tests/__pycache__/
	rm -f .coverage
	find . -name "*.pyc" -delete