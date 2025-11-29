.PHONY: install test lint build clean

install:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest tests/ -v --tb=short

lint:
	flake8 app.py tests/
	black --check app.py tests/

format:
	black app.py tests/

build:
	docker build -t landing-page:latest .

run:
	python app.py

clean:
	rm -rf __pycache__ .pytest_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
