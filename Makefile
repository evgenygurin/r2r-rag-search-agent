.PHONY: help install sync lint fix format typecheck test clean run dev

help:
	@echo "R2R FastMCP - Available commands:"
	@echo ""
	@echo "  make install    - Install all dependencies (production + dev)"
	@echo "  make sync       - Sync dependencies from pyproject.toml"
	@echo "  make dev        - Install in development mode"
	@echo "  make lint       - Run ruff and mypy checks"
	@echo "  make fix        - Auto-fix ruff issues"
	@echo "  make format     - Format code with ruff"
	@echo "  make typecheck  - Run mypy type checking"
	@echo "  make run        - Run MCP server"
	@echo "  make clean      - Remove cache files and venv"
	@echo ""

install:
	@echo "Installing dependencies via uv..."
	uv sync --all-extras

sync:
	@echo "Syncing dependencies..."
	uv sync

dev:
	@echo "Installing dev dependencies..."
	uv sync --extra dev

lint: format typecheck
	@echo "✅ All checks passed"

fix:
	@echo "Fixing code issues..."
	uv run ruff check --fix server.py

format:
	@echo "Formatting code..."
	uv run ruff format server.py
	uv run ruff check server.py

typecheck:
	@echo "Type checking..."
	uv run mypy server.py

run:
	@echo "Starting R2R MCP server..."
	uv run python server.py

clean:
	@echo "Cleaning cache and virtual environment..."
	rm -rf __pycache__
	rm -rf .venv
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
