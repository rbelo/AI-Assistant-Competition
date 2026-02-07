# Test Coverage Analysis

## Current State

**Overall coverage: 17.4%** (target: 50%)

| Module | Stmts | Miss | Branch | Cover | Status |
|--------|-------|------|--------|-------|--------|
| `schedule.py` | 20 | 0 | 8 | **100%** | Well tested |
| `student_utils.py` | 49 | 5 | 20 | **91%** | Well tested |
| `email_service.py` | 68 | 30 | 8 | **55%** | Partially tested |
| `database_handler.py` | 1006 | 849 | 222 | **14%** | Undertested |
| `negotiations.py` | 347 | 293 | 158 | **14%** | Undertested |
| `student_playground.py` | 103 | 103 | 22 | **0%** | No tests |
| `sidebar.py` | 51 | 51 | 26 | **0%** | No tests |
| `negotiation_display.py` | 23 | 23 | 10 | **0%** | No tests |
| `game_modes.py` | 9 | 9 | 0 | **0%** | No tests |

## What's Already Well Tested

- **`schedule.py`** (100%): Berger round-robin algorithm has thorough tests covering even/odd team counts, edge cases, and invariant properties.
- **`student_utils.py`** (91%): CSV column normalization and parsing well tested across delimiter types, case variations, and edge cases.
- **`email_service.py`** (55%): Email validation (`valid_email`) and secret accessor functions (`get_mail`, `get_mail_api_pass`, `get_app_link`) are tested. Missing: password reset flow and email sending.
- **Scoring functions in `negotiations.py`**: `compute_deal_scores` and `parse_team_name` have dedicated unit tests.
- **DB storage in `database_handler.py`**: `insert_negotiation_chat`, `get_negotiation_chat`, `insert_student_prompt`, `get_student_prompt`, `fetch_and_compute_scores_for_year`, `fetch_and_compute_scores_for_year_game`, and `get_error_matchups` are tested.

## Recommended Improvements (Priority Order)

### 1. `negotiations.py` -- Pure Functions (High Priority, High Impact)

This module contains many **pure or near-pure functions** that are straightforward to unit test without mocking external services. These functions implement core business logic for the negotiation system.

**Functions to test:**

| Function | Lines | Why |
|----------|-------|-----|
| `clean_agent_message(agent_name_1, agent_name_2, message)` | 17-27 | Regex cleaning of agent name prefixes from messages. Edge cases: empty messages, names with special regex chars, case insensitivity. |
| `_build_summary_context(chat_history, ...)` | 30-45 | Builds summary text from chat history. Test with empty history, `None` history_size, various history sizes. |
| `_extract_summary_text(summary_eval, summary_agent_name)` | 48-57 | Extracts text from a summary evaluation object. Test with empty eval, missing agent name, multiple entries. |
| `parse_deal_value(summary_text, summary_termination_message)` | 60-77 | Parses numeric deal values from summary text. Critical business logic -- test with dollar signs, commas, negative values, missing values, multiple numbers. |
| `extract_summary_from_transcript(transcript, ...)` | 101-113 | Extracts summary section from full transcript. Test with empty transcript, missing termination message, multi-part transcripts. |
| `resolve_initiator_role_index(name_roles, conversation_order)` | 312-328 | Resolves which role starts the conversation. Test "same", "opposite", role name matching, empty/None input. |
| `get_role_agent(team, role_index)` | 331-336 | Gets agent by role index. Test valid indices (1, 2) and invalid indices. |
| `get_minimizer_reservation(team)` / `get_maximizer_reservation(team)` | 339-344 | Simple accessors. Quick tests for correctness. |
| `get_minimizer_maximizer(initiator_team, responder_team, ...)` | 347-350 | Determines team roles based on initiator role index. Test both directions. |
| `is_valid_termination(msg, history, ...)` | 353-406 | Complex validation: checks termination phrase, agreement indicators, and value consistency. High bug risk -- test edge cases around the 5% threshold, missing indicators, empty history. |
| `build_llm_config(model, api_key, ...)` | 409-414 | Builds LLM config dict. Test gpt-5 vs non-gpt-5 models (temperature/top_p conditional). |
| `is_invalid_api_key_error(error)` | 417-426 | Pattern matching on error messages. Test each recognized pattern and non-matching errors. |

**Estimated impact:** Testing these functions alone would add coverage for ~130 statements and ~50 branches, pushing `negotiations.py` from 14% toward 50%+.

### 2. `database_handler.py` -- CRUD Operations (High Priority, Highest Impact)

At 1,006 statements, this is by far the largest module and the biggest driver of the coverage gap. The existing tests demonstrate a good pattern (mock `get_connection`, assert on queries and params) that can be replicated for the remaining ~50 untested functions.

**Highest-value functions to test:**

| Function | Lines | Why |
|----------|-------|-----|
| `get_db_connection_string()` | 15-23 | Tests env var vs `st.secrets` fallback. Simple to test with monkeypatching. |
| `authenticate_user(email, password_hash)` | 1347-1369 | **Security-critical.** Verify correct query, return value on match/no match. |
| `exists_user(email)` | 1421-1443 | Used by password reset flow. Test found/not-found cases. |
| `insert_student_data(...)` | 615-659 | Student enrollment. Verify query params, temp password hashing, error handling. |
| `populate_plays_table(game_id, ...)` | 84-135 | Game initialization. Two branches: specific class vs all classes (`_`). |
| `store_game_in_db(...)` | 424-497 | Game creation. Verify transaction (insert game + config + parameters). |
| `update_game_in_db(...)` | 331-388 | Game update. Test partial updates and the conditional query building. |
| `get_group_id_from_user_id(user_id)` | 501-516 | User lookup. Test found/not-found. |
| `get_class_from_user_id(user_id)` | 539-554 | User lookup. Test found/not-found. |
| `get_academic_year_from_user_id(user_id)` | 520-535 | User lookup. Test found/not-found. |
| `remove_student(user_id)` | 558-576 | Student deletion. Verify cascade delete query. |
| `store_group_values(...)` | 2220-2265 | Group value storage. Verify upsert query. |
| `get_group_values(game_id, ...)` | 2317-2336 | Group value retrieval. Test found/not-found. |
| `get_all_group_values(game_id)` | 2372-2396 | Batch retrieval. Test empty results and multiple rows. |
| `upsert_game_simulation_params(...)` | 886-968 | Complex upsert for simulation config. Many optional params. |
| `get_game_simulation_params(game_id)` | 971-1013 | Config retrieval with column-to-dict mapping. |
| `insert_playground_result(...)` | 1036-1148 | Playground result storage. Complex function with conditional fields. |
| `get_playground_results(...)` | 1151-1232 | Playground result retrieval with ordering. |
| `update_password(email, new_password)` | 1447-1466 | **Security-critical.** Verify password update query. |
| API key CRUD (`list_user_api_keys`, `add_user_api_key`, `update_user_api_key`, `delete_user_api_key`, `get_user_api_key`) | 1484-1653 | **Security-critical.** Encrypted API key storage. Verify encryption/decryption. |
| `update_round_data(...)` | 1742-1814 | Round data updates. Complex conditional logic (team1_role1 vs team1_role2). |

**Estimated impact:** Even testing just the 10 most critical functions would add coverage for ~200+ statements, potentially pushing the module from 14% to ~35%.

### 3. `email_service.py` -- Remaining Functions (Medium Priority)

Currently at 55%, the untested portion contains the password reset flow.

**Functions to test:**

| Function | Lines | Why |
|----------|-------|-----|
| `set_password(email)` | 55-59 | Orchestrates password reset. Test three paths: user exists (email sent), user exists (email fails), user not found (returns None). Mock `exists_user` and `send_set_password_email`. |
| `generate_set_password_link(email)` | 92-101 | JWT link generation. Verify token contains correct payload, URL format is correct. Mock `get_base_url`. |
| `send_set_password_email(email, link)` | 63-80 | Email sending via SMTP. Mock `smtplib.SMTP` to verify the MIME message structure, login, and sendmail calls. Test exception handling. |
| `get_base_url()` | 87-88 | Thin wrapper. Quick test. |

**Estimated impact:** Would bring `email_service.py` from 55% to ~95%.

### 4. `student_playground.py` -- Testable Logic (Medium Priority)

Currently at 0%. The module mixes pure logic with Streamlit UI code. Focus on the testable parts:

**Functions to test:**

| Function | Lines | Why |
|----------|-------|-----|
| `clean_agent_message(...)` | 27-37 | Same regex logic as `negotiations.py`. If you test it there, you still need to verify this copy works identically. |
| `save_playground_results(...)` | 105-114 | Thin wrapper around `insert_playground_result`. Verify correct parameter passing. |
| `load_playground_results(...)` | 118-119 | Thin wrapper around `get_playground_results`. Verify correct parameter passing. |

**Note:** `run_playground_negotiation` (lines 41-101) and `display_student_playground` (lines 123-288) require mocking AutoGen and Streamlit respectively. Testing them is possible but lower ROI.

### 5. `negotiation_display.py` -- Rendering Logic (Low Priority)

At 0% and 23 statements, this is a single function that renders negotiation results using Streamlit widgets. It can be tested by mocking `st` and asserting the correct methods are called with the correct arguments. The function has meaningful branching logic (deal_value == None vs -1 vs valid).

### 6. `sidebar.py` and `game_modes.py` (Low Priority)

These are pure Streamlit UI code with minimal business logic. Testing them requires extensive Streamlit mocking for low returns. Consider these only after reaching the 50% target.

## Recommended Test Implementation Order

To reach the 50% coverage target most efficiently:

1. **`negotiations.py` pure functions** -- Add ~12 test functions covering the functions listed above. These are the easiest to write (no mocking needed for most) and cover core business logic.

2. **`database_handler.py` CRUD operations** -- Add ~15-20 test functions following the existing pattern in `test_negotiation_chat_storage.py` (mock connection, assert query and params). Prioritize security-critical functions (`authenticate_user`, `update_password`, API key CRUD).

3. **`email_service.py` password reset** -- Add ~5 test functions. Mock `smtplib` and `jwt`.

4. **`student_playground.py` pure functions** -- Add ~3 test functions for the non-UI logic.

5. **`negotiation_display.py`** -- Add ~3 test functions with mocked Streamlit.

## Structural Recommendations

- **Code duplication:** `clean_agent_message()` is duplicated identically in `negotiations.py` and `student_playground.py`. Consider extracting it to a shared utility module -- this also makes it easier to test once.
- **Test organization:** The existing pattern of one test file per module works well. Suggested new files:
  - `tests/unit/test_negotiations_logic.py` -- for the pure functions in `negotiations.py`
  - `tests/unit/test_database_crud.py` -- for the DB CRUD operations
  - `tests/unit/test_email_password_reset.py` -- for password reset flow
  - `tests/unit/test_playground_logic.py` -- for playground pure functions
- **Coverage threshold:** The current 50% target in `pyproject.toml` is reasonable. Once reached, consider gradually increasing to 60-70%.
