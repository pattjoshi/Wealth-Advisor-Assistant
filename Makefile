.PHONY: help install run lint format test evaluate ui docker-build clean

help:
	@echo "Targets: install run lint format test evaluate ui docker-build clean"

install:
	pip install -e ".[dev]"

run:
	python -m wealth_advisor.cli run --client client_001

lint:
	ruff check .

format:
	ruff format .

test:
	pytest

evaluate:
	python scripts/evaluate.py

ui:
	streamlit run ui/streamlit_app.py

docker-build:
	docker build -t wealth-advisor .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov build dist *.egg-info
