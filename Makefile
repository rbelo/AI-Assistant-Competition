# Makefile for AI Assistant Competition
# Run 'make help' to see available commands
#
# This project uses 'uv' for fast dependency management.
# All commands work without manually activating the virtual environment.

.PHONY: help install install-dev test test-unit test-e2e test-integration test-cov lint lint-fix format check run run-dev clean venv

# Default target
help:
	@echo "AI Assistant Competition - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make venv          Create virtual environment (first time setup)"
	@echo "  make install       Install production dependencies"
	@echo "  make install-dev   Install all dependencies (including dev tools)"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run all tests"
	@echo "  make test-unit     Run only unit tests (fast, no external deps)"
	@echo "  make test-e2e      Run E2E tests (requires app running)"
	@echo "  make test-integration  Run integration tests"
	@echo "  make test-cov      Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          Check code style (ruff + black)"
	@echo "  make lint-fix      Auto-fix linting issues"
	@echo "  make format        Format code with black"
	@echo "  make check         Run lint + tests (CI simulation)"
	@echo ""
	@echo "Application:"
	@echo "  make run           Start the Streamlit application"
	@echo "  make run-dev       Start app with auto-login (no authentication)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean         Remove cache and build artifacts"

# Create virtual environment (first time setup)
venv:
	uv venv --python 3.12
	@echo ""
	@echo "Virtual environment created! Now run: make install-dev"

# Setup commands (using uv for speed)
install:
	uv pip install -r streamlit/requirements.txt

install-dev:
	uv pip install -e ".[dev]"
	uv pip install -r streamlit/requirements.txt
	@echo ""
	@echo "Development dependencies installed!"
	@echo "Run 'make check' to verify setup."

# Testing commands (uv run automatically uses the venv)
test:
	PYTHONPATH="$(CURDIR):$(CURDIR)/streamlit" uv run pytest tests -v

test-unit:
	PYTHONPATH="$(CURDIR):$(CURDIR)/streamlit" uv run pytest tests/unit -v

test-e2e:
	@echo "Note: Make sure the app is running (make run) in another terminal"
	PYTHONPATH="$(CURDIR):$(CURDIR)/streamlit" uv run pytest tests/e2e -v

test-integration:
	PYTHONPATH="$(CURDIR):$(CURDIR)/streamlit" uv run pytest tests -v -m "integration"

test-cov:
	PYTHONPATH="$(CURDIR):$(CURDIR)/streamlit" uv run pytest tests -v --cov=streamlit/modules --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "Coverage report generated: htmlcov/index.html"

# Code quality commands
lint:
	uv run ruff check streamlit tests
	uv run black --check streamlit tests

lint-fix:
	uv run ruff check --fix streamlit tests
	uv run black streamlit tests

format:
	uv run black streamlit tests

# Combined check (for CI)
check: lint test-unit
	@echo ""
	@echo "All checks passed!"

# Application
run:
	cd streamlit && uv run streamlit run 0_Home.py

# Development mode with auto-login (no authentication required)
run-dev:
	cd streamlit && DEV_AUTO_LOGIN=1 DEV_IS_INSTRUCTOR=true uv run streamlit run 0_Home.py

# Maintenance
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "Cleaned up cache and build artifacts"
