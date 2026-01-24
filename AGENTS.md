# Repository Guidelines

## Primary Guidance
Read `CLAUDE.md` first and treat it as the primary project guidelines. Use this file only for supplemental notes.

## Project Structure & Module Organization
The Streamlit app lives in `streamlit/`, with `0_Home.py` as the main entry point and feature pages under `streamlit/pages/`. Shared services (database connectivity, Google Drive integration, game logic, metrics) reside in `streamlit/modules/`. Integration assets, including derived models and SQL templates, live under `database/`, while supporting docs go in `documentation/`. Tests target business flows in `tests/`. Keep large data files out of the repo; mount them via Drive through `streamlit/modules/drive_file_manager.py`.

## Build, Test, and Development Commands
Use Makefile targets for setup, running, testing, and linting to keep tooling consistent across environments. Prefer `make venv`, `make install-dev`, `make run`, `make run-dev`, and the `make test*`/`make lint*` targets over direct `python`, `pip`, or `streamlit` invocations.

## Coding Style & Naming Conventions
We follow standard Python 3.10+ conventions: four-space indentation, type-hinted public functions, and descriptive snake_case module and function names. Page scripts should export top-level Streamlit components only; move supporting logic into `streamlit/modules/`. Keep secrets and credentials in `.streamlit/secrets.toml` and access them through `st.secrets`. Prefer explicit imports over wildcard usage.

## Testing Guidelines
Pytest is the default framework; structure new tests under `tests/` mirroring the module layout (`tests/test_metrics_handler.py`, etc.). When a test touches Drive or database features, mock external calls using `unittest.mock` as seen in `tests/unit_tests.py`. Aim to cover new service functions with deterministic unit tests and add Streamlit interaction smoke tests when UI changes alter session-state.

## Commit & Pull Request Guidelines
Commit messages follow a lightweight Conventional Commit style observed in recent history (`fix:`, `feat:`, `chore:`). Limit each commit to a focused change set and describe the observable behavior. Pull requests should include: a one-paragraph summary, testing evidence (`pytest`, screenshots for UI shifts), linked issues or task IDs, and any configuration steps for reviewers. Keep secrets out of diffs and confirm Drive tokens are redacted.

## Configuration & Secrets
Copy `streamlit/.streamlit/secrets.example.toml` to `secrets.toml` and fill project-specific values. Never commit populated secrets. For local databases, use `.env` files referenced by `DATABASE_URL` to avoid rewriting service credentials.
