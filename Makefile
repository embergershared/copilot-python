.PHONY: install install-dev lint format type-check test coverage run security container-build container-run

PYTHON ?= python

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev,azure]"

lint:
	ruff check .

format:
	ruff format .

type-check:
	mypy

test:
	pytest

coverage:
	pytest --cov=copilot_python_app --cov-report=html --cov-report=term-missing

run:
	$(PYTHON) src/main.py serve --host 0.0.0.0 --port 8000 --reload

security:
	bandit -r src
	pip-audit

container-build:
	docker build -t copilot-python-app:local .

container-run:
	docker compose up --build


