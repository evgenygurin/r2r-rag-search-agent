.PHONY: help install sync lint fix format typecheck test clean run run-openapi run-http run-gemini run-inspector dev

help:
	@echo "R2R FastMCP - Available commands:"
	@echo ""
	@echo "  make install      - Install all dependencies (production + dev)"
	@echo "  make sync         - Sync dependencies from pyproject.toml"
	@echo "  make dev          - Install in development mode"
	@echo "  make lint         - Run ruff and mypy checks"
	@echo "  make fix          - Auto-fix ruff issues"
	@echo "  make format       - Format code with ruff"
	@echo "  make typecheck    - Run mypy type checking"
	@echo ""
	@echo "  make run          - Run custom MCP server (server.py)"
	@echo "  make run-openapi  - Run OpenAPI MCP server in stdio mode"
	@echo "  make run-http     - Run OpenAPI MCP server in HTTP mode (port 8000)"
	@echo "  make run-gemini   - Run Gemini integration test"
	@echo "  make run-inspector - Run MCP Inspector (GUI for testing tools)"
	@echo ""
	@echo "  make clean        - Remove cache files and venv"
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
	@echo "Starting custom R2R MCP server (server.py)..."
	uv run python server.py

run-openapi:
	@echo "Starting OpenAPI R2R MCP server in stdio mode..."
	@echo "Use Ctrl+C to stop"
	uv run python r2r_openapi_server.py

run-http:
	@echo "Starting OpenAPI R2R MCP server in HTTP mode on port 8000..."
	@echo "Access at http://localhost:8000/mcp"
	@echo "Use Ctrl+C to stop"
	uv run uvicorn r2r_openapi_server:app --reload --host 127.0.0.1 --port 8000

run-gemini:
	@echo "Running Gemini integration test..."
	@echo "Make sure GEMINI_API_KEY is set in .env"
	@read -p "Enter query: " query; \
	uv run python r2r_openapi_server.py --gemini "$$query"

run-inspector:
	@echo "Starting MCP Inspector..."
	@echo "This will open a web interface at http://localhost:5173"
	@echo "Use Ctrl+C to stop"
	@echo ""
	npx @modelcontextprotocol/inspector uv run python r2r_openapi_server.py

clean:
	@echo "Cleaning cache and virtual environment..."
	rm -rf __pycache__
	rm -rf .venv
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
