# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Assistant Competition is a learning platform for students to build AI agents that compete in negotiation challenges. Part of the "AI Impact on Business" course at Nova SBE.

**Tech Stack:** Streamlit frontend, PostgreSQL database, Microsoft AutoGen for multi-agent orchestration, OpenAI for LLM integration.

## Development Commands

This project uses **uv** for fast dependency management. All `make` commands work without manually activating the virtual environment.

**Python version:** 3.9 to 3.13 (3.12 recommended). AutoGen requires Python < 3.14.

**Command policy:** Use Makefile targets for all common workflows (setup, run, test, lint) to keep tooling consistent.

```bash
# First-time setup
make venv                                        # Create virtual environment with Python 3.12
make install-dev                                 # Install all dependencies

# Run application
make run                                         # Start Streamlit app
make run-dev                                     # Start with auto-login (no auth)

# Testing
make test                                        # Run all tests
make test-unit                                   # Run unit tests only (fast)
make test-e2e                                    # Run E2E tests (requires app running)
make test-cov                                    # Run tests with coverage report

# Code Quality
make lint                                        # Check code style
make lint-fix                                    # Auto-fix linting issues
make format                                      # Format code with black
make check                                       # Run lint + tests (CI simulation)

# Pre-commit hooks (optional)
uv run pre-commit install                        # Install hooks
uv run pre-commit run --all-files                # Run manually

# Database setup
createdb ai_assistant_competition
psql -d ai_assistant_competition -f database/Tables_AI_Negotiator.sql
```

**Note for Claude:** Use Makefile targets whenever available. If a command is not covered by Make, use `uv run` for Python commands (e.g., `uv run pytest`, `uv run python script.py`).

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (mocks for Streamlit, DB, external APIs)
├── unit/                    # Fast tests, no external deps
│   ├── test_control_panel_ui_helpers.py  # Control-panel helper behavior
│   ├── test_database_crud.py             # Database CRUD wrapper tests
│   ├── test_schedule.py         # Berger algorithm tests
│   ├── test_email.py            # Email validation tests
│   ├── test_negotiations_logic.py       # Negotiation orchestration/utilities
│   └── test_negotiations_scoring.py     # Deal scoring behavior
├── integration/             # Tests with mocked external services
│   └── test_openai_latency.py   # Optional live API latency check
└── e2e/                     # End-to-end Playwright tests
    ├── conftest.py              # E2E fixtures (instructor_page, simulation_test_game)
    ├── test_game_creation.py    # Game creation flow
    ├── test_add_student.py      # Student management flow
    └── test_run_simulation.py   # Simulation execution flow
```

**Test Markers:**
- `@pytest.mark.unit` - Fast, no external deps
- `@pytest.mark.integration` - May need mocked external services
- `@pytest.mark.e2e` - Playwright browser tests (requires app running)
- `@pytest.mark.requires_db` - Needs database connection
- `@pytest.mark.requires_secrets` - Needs secrets.toml

**E2E Test Environment Variables:**
- `E2E_INSTRUCTOR_EMAIL` / `E2E_INSTRUCTOR_PASSWORD` - Instructor login credentials
- `E2E_OPENAI_API_KEY` - For simulation tests

## Architecture

**Entry Point:** `streamlit/0_Home.py` - authentication and landing page

**Pages** (`streamlit/pages/`):
- `1_Play.py` - Main game interface with leaderboards and game selection
- `2_Control_Panel.py` - Admin panel entrypoint (state + tab orchestration delegated to modules)
- `3_Playground.py` - Student agent testing environment
- `4_Profile.py` - User profile management

**Core Modules** (`streamlit/modules/`):
- `database_handler.py` - All PostgreSQL operations via parameterized queries
- `negotiations.py` - Public negotiation orchestration facade used by pages
- `negotiations_common.py` - Shared negotiation utilities (scoring, role resolution, termination checks, API config)
- `negotiations_agents.py` - Agent construction from submitted prompts and reservation values
- `negotiations_summary.py` - Deal-summary generation/parsing helpers
- `negotiations_run_helpers.py` - Simulation timing/diagnostic summarization helpers
- `schedule.py` - Berger round-robin tournament scheduling algorithm
- `student_utils.py` - CSV processing for bulk student import (normalizes column headers)
- `student_playground.py` - Logic for testing agent prompts before submission
- `control_panel/` - Modularized instructor UI tabs and state management (`setup`, `submissions`, `simulation`, `results`)
- `control_panel_ui_helpers.py` - Shared formatting/parsing/progress helpers for Control Panel UI

**Data Flow:** Streamlit UI → Session State → Business Logic (modules) → Database/External Services

## Game System

**Game Types:** Zero-sum negotiation (buyer/seller) and Prisoner's Dilemma

**Student Prompt Format:** Two prompts separated by `#_;:)` delimiter - first for role 1, second for role 2. Stored in PostgreSQL (`student_prompt` table).

**Negotiation Flow:**
1. Instructor creates game with roles (e.g., "Buyer", "Seller") and value ranges
2. Students submit prompts for both roles via Playground
3. Instructor runs negotiations - agents are created via AutoGen `ConversableAgent`
4. `create_agents()` loads prompts from PostgreSQL, creates agent pairs with termination message handling
5. `create_chats()` runs round-robin matches using Berger schedule
6. Summary agent evaluates deal outcome, scores calculated and stored in `round` table

**Scoring:** Each match produces scores based on negotiated deal value relative to private values. Failed negotiations (no valid deal) score 0.

## Key Conventions

- Page scripts export top-level Streamlit components only; supporting logic goes in `streamlit/modules/`
- Secrets in `.streamlit/secrets.toml`, accessed via `st.secrets`
- Environment-specific DB URLs can be sourced from `.env` (Makefile auto-loads) and/or `streamlit/.streamlit/secrets.toml`
- Mock external calls (database/APIs) using `unittest.mock` in tests
- Commit messages use Conventional Commits style: `feat:`, `fix:`, `refactor:`, `chore:`

## Database Schema

Main tables: `user_`, `instructor`, `game`, `group_values`, `plays`, `round`, `game_modes`
Game configs: `zero_sum_game_config`, `prisoners_dilemma_config`
Metrics: `page_visit`, `game_interaction`, `prompt_metrics`, `conversation_metrics`, `deal_metrics`

Students organized by `academic_year`, `class`, and `group_id`. Connection string via `st.secrets["database"]["url"]`.

**CSV Import Format:** `user_id;email;group_id;academic_year;class` - column names are normalized (accepts variations like "userID", "e-mail", etc.)
