.PHONY: help install install-dev run test lint format docker-build docker-run clean

PYTHON := python3
PIP := $(PYTHON) -m pip
FLASK := $(PYTHON) -m flask
DOCKER := docker

help:
	@echo "Available targets:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  run          - Run the Flask development server"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linters (flake8)"
	@echo "  format       - Format code with black"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  clean        - Remove build artifacts"

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements.txt -r requirements-dev.txt

run:
	FLASK_APP=app.py FLASK_ENV=development $(FLASK) run --host=0.0.0.0 --port=8080

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m flake8 app.py --max-line-length=100

format:
	$(PYTHON) -m black app.py --line-length=100

docker-build:
	$(DOCKER) build -t gitapp-callback:latest .

docker-run:
	$(DOCKER) run -p 8080:8080 \
		-e SECRET_KEY=dev-secret-key \
		-e GITHUB_APP_NAME=calypr-workflows \
		gitapp-callback:latest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
