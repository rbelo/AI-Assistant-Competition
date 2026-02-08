# Repository Guidelines

This file is the single canonical contributor guide for this repository.

## Project Overview
AI Assistant Competition is a learning platform for students to build AI agents that compete in negotiation challenges as part of the "AI Impact on Business" course at Nova SBE.

**Tech Stack:** Streamlit frontend, PostgreSQL database, Microsoft AutoGen for multi-agent orchestration, OpenAI for LLM integration.

## Project Structure & Module Organization
The Streamlit app lives in `streamlit/`, with `0_Home.py` as the main entry point and feature pages under `streamlit/pages/`.

Shared services live in `streamlit/modules/`:
- `database_handler.py` for PostgreSQL operations.
- `negotiations.py` plus `negotiations_*` helpers for orchestration, scoring, summaries, and diagnostics.
- `control_panel/` modules for instructor UI composition (`setup`, `submissions`, `simulation`, `results`).
- `control_panel_ui_helpers.py` for shared UI formatting/parsing/progress helpers.
- `schedule.py` for Berger scheduling.
- `student_utils.py` for CSV normalization/processing.

Supporting assets:
- `database/` for schema and seed SQL.
- `documentation/` for guides and runbooks.
- `tests/` for `unit`, `integration`, and `e2e` test suites.

## Build, Test, and Development Commands
Use Makefile targets for setup, running, testing, and linting to keep workflows consistent.

Preferred commands:
- `make venv`
- `make install-dev`
- `make run`
- `make run-dev-admin`
- `make run-dev-student`
- `make test`, `make test-unit`, `make test-e2e`, `make test-cov`
- `make lint`, `make lint-fix`, `make format`, `make check`

Use `uv run ...` only when there is no matching Make target.

## Testing Guidelines
Pytest is the default framework.

Test layout:
- `tests/unit/` for deterministic fast tests.
- `tests/integration/` for mocked external-service flows.
- `tests/e2e/` for Playwright end-to-end coverage.

Markers:
- `@pytest.mark.unit`
- `@pytest.mark.integration`
- `@pytest.mark.e2e`
- `@pytest.mark.requires_db`
- `@pytest.mark.requires_secrets`

When tests touch DB or API features, mock external calls using `unittest.mock` (as in `tests/unit/`).

## Architecture
Entry point: `streamlit/0_Home.py`.

Pages:
- `streamlit/pages/1_Play.py`
- `streamlit/pages/2_Control_Panel.py`
- `streamlit/pages/3_Playground.py`
- `streamlit/pages/4_Profile.py`

Data flow:
- Streamlit UI -> session state -> module logic -> database/external services.

## Game System
Game types:
- Zero-sum negotiation
- Prisoner's Dilemma

Student prompt format:
- Two prompts separated by `#_;:)` (role 1 then role 2), stored in PostgreSQL (`student_prompt`).

Negotiation flow:
1. Instructor creates game with roles and value ranges.
2. Students submit prompts via Playground.
3. Instructor runs simulations (AutoGen agents).
4. `create_agents()` loads prompts from PostgreSQL.
5. `create_chats()` runs Berger round-robin matches.
6. Summary agent evaluates deal outcome; scores are stored in `round`.

Scoring:
- Based on deal value relative to each side's reservation values.
- Failed negotiations score zero.

## Coding Style & Conventions
- Python 3.10+ style with four-space indentation.
- Type-hint public functions when practical.
- Use descriptive snake_case names.
- Keep page scripts as top-level Streamlit composition; move supporting logic to `streamlit/modules/`.
- Prefer explicit imports over wildcard imports.
- Always evaluate whether logic can be abstracted and reused before introducing duplicate code.

## Configuration & Secrets
- Copy `streamlit/.streamlit/secrets.example.toml` to `streamlit/.streamlit/secrets.toml` for local setup.
- Never commit populated secrets.
- Use `.env` for local DB and environment-specific values.
- Runtime DB connection resolves from `DATABASE_URL` or `st.secrets["database"]["url"]`.

Common environment variables:
- `DATABASE_URL`
- `PRODUCTION_DATABASE_URL`
- `STAGING_DATABASE_URL`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD_HASH`
- `API_KEY_ENCRYPTION_KEY`
- `E2E_INSTRUCTOR_EMAIL`, `E2E_INSTRUCTOR_PASSWORD`, `E2E_OPENAI_API_KEY`

## Commit & Pull Request Guidelines
- Use lightweight Conventional Commit style (`feat:`, `fix:`, `refactor:`, `chore:`).
- Keep commits focused and behavior-oriented.
- PRs should include:
  - One-paragraph summary.
  - Testing evidence (pytest output, screenshots for UI changes).
  - Linked issue/task IDs.
  - Any reviewer setup/config notes.
- Keep secrets out of diffs and redact credentials/tokens.

## Versioning
- App version format: `vYYYY-MM-DD.N` (example: `v2026-02-07.0`).
- For same-day fixes, increment `N` (`.1`, `.2`, ...).
- On a new date, reset to `.0`.
- Keep the displayed app version and release tag aligned.
- Before creating any commit, ask the user whether they want to update the app version.
