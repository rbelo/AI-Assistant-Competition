# Provider-Aware API Keys (OpenAI/OpenRouter/Custom) - Implementation Plan

## Summary
Add provider metadata to saved user API keys and thread it into runtime LLM config so a selected key determines both `api_key` and `base_url`. Keep existing keys working by defaulting them to OpenAI. For non-OpenAI providers, switch model input from fixed dropdown to free-text.

## Confirmed Product Decisions
1. Provider schema: `provider enum + optional base_url`.
2. Model UX: OpenAI uses existing dropdown; non-OpenAI uses free-text model input.
3. Backward compatibility: existing keys default to OpenAI automatically.
4. Endpoint rule: OpenRouter URL is fixed to `https://openrouter.ai/api/v1` and not user-editable.

## Public Interfaces / Type Changes
1. `user_api_key` table gains:
- `provider VARCHAR(20) NOT NULL DEFAULT 'openai'`
- `base_url TEXT NULL`
- `CHECK (provider IN ('openai','openrouter','custom'))`

2. `streamlit/modules/database_handler.py` function signatures:
- `add_user_api_key(user_id, key_name, api_key, provider="openai", base_url=None)`
- `update_user_api_key(user_id, key_id, new_name, api_key, provider="openai", base_url=None)`
- `list_user_api_keys(user_id)` returns metadata including `provider` and `base_url`.
- Add new accessor: `get_user_api_key_record(user_id, key_id)` returning `{api_key, provider, base_url}`.
- Keep `get_user_api_key(user_id, key_id)` as compatibility helper returning decrypted string only.

3. Runtime config assembly:
- Add helper in `streamlit/modules/llm_provider.py` or `streamlit/modules/negotiations_common.py`:
`resolve_provider_base_url(provider, base_url)` with rules:
`openai -> None`, `openrouter -> https://openrouter.ai/api/v1`, `custom -> base_url`.
- Call `build_llm_config(model, api_key, base_url=resolved_base_url)` everywhere keys are consumed.

## Implementation Plan

### 1. Database migration and bootstrap safety
1. Update `database/Tables_AI_Negotiator.sql` table definition for new columns/check.
2. Enhance `_ensure_user_api_key_table(cur)` to run idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` and backfill:
`UPDATE user_api_key SET provider='openai' WHERE provider IS NULL`.
3. Ensure constraints/defaults are in place for existing environments without manual migration scripts.

### 2. CRUD updates
1. Update insert/update SQL to persist provider and base URL.
2. In write path, normalize stored values:
- `openai`: persist `base_url=NULL`.
- `openrouter`: persist fixed URL.
- `custom`: persist trimmed URL; reject empty.
3. Extend `list_user_api_keys` select and returned dictionaries with provider/base URL.
4. Implement `get_user_api_key_record` combining decrypt + metadata retrieval.

### 3. Profile UI (`streamlit/pages/4_Profile.py`)
1. In "Add API key" dialog:
- Add provider select: `OpenAI`, `OpenRouter`, `Custom`.
- Label key field as generic "API key" (not "OpenAI API key").
- Show `base_url` input only for `Custom`.
- Display hint text: OpenAI gets keys from OpenAI; OpenRouter uses fixed endpoint.
2. In "Edit API key" dialog:
- Load provider/base URL from selected key metadata.
- Allow provider change.
- For OpenRouter hide URL input and enforce fixed endpoint.
- For OpenAI clear URL.
3. Saved key select display:
- Show provider in label, e.g. `E2E Key (OpenRouter)`.
- Keep unique mapping by `key_id`, not label string.
4. Validation messages:
- Custom provider requires URL.
- Duplicate name behavior unchanged (`UNIQUE (user_id, key_name)`).

### 4. Playground wiring (`streamlit/pages/3_Playground.py`)
1. Replace current secret fetch:
- From `get_user_api_key(...)` to `get_user_api_key_record(...)`.
2. Resolve provider URL and pass into:
- negotiation engine config
- summary engine config
3. Model input behavior:
- If selected key provider is `openai`: keep existing `MODEL_OPTIONS` dropdown.
- Else: show text input `Model` with sensible default:
`openrouter/auto` for openrouter, blank-required for custom.
4. Guardrails:
- Disable Run if non-openai provider and model text empty.

### 5. Control Panel simulation wiring (`streamlit/modules/control_panel/game_overview_simulation.py`)
1. Same key-record retrieval and base-url resolution for:
- Run Simulation tab
- Error Chats tab
2. Same model UX split:
- OpenAI dropdown for OpenAI keys.
- Free-text model for non-OpenAI keys.
3. Keep persisted simulation params format unchanged unless explicitly needed:
- continue storing `model` only; provider comes from selected key at execution time.

### 6. Utility and constants
1. Add provider constants in one module:
- `SUPPORTED_KEY_PROVIDERS`
- `OPENROUTER_BASE_URL`
2. Add formatting helper for provider labels in UI.
3. Add URL normalization helper for custom endpoints (trim, strip trailing slash optional).

### 7. Documentation updates
1. Update Profile copy from "OpenAI API key" to provider-neutral wording.
2. Add short section to `documentation/`:
- how to add OpenRouter key
- model entry expectations for non-OpenAI providers
- custom endpoint requirements.

## Test Plan
1. Unit tests for CRUD metadata
- `add_user_api_key` stores provider/base_url normalization rules.
- `update_user_api_key` updates provider transitions correctly.
- `list_user_api_keys` returns provider/base_url.
- `get_user_api_key_record` decrypts key and returns metadata.
- legacy `get_user_api_key` still returns string.

2. Unit tests for provider resolution
- openai -> `base_url=None`
- openrouter -> fixed URL
- custom -> uses provided URL
- invalid provider rejected.

3. Unit tests for UI decision helpers
- selected provider drives model control type.
- provider label rendering for saved keys.
- custom provider requires non-empty URL.

4. Integration tests
- Playground run path builds `LLMConfig` with resolved base URL from selected key metadata.
- Simulation run path does the same for both main run and error chats.

5. E2E adjustments
- Update selectors from `OpenAI API key` to `API key`.
- Add one E2E scenario for adding an OpenRouter key and verifying provider tag appears in selected key UI.
- Keep existing OpenAI flow green as regression baseline.

## Rollout and Compatibility
1. Deploy code with idempotent `_ensure_user_api_key_table` alterations first.
2. Existing rows automatically behave as OpenAI due default/backfill.
3. No mandatory user migration step.
4. Existing simulations/playground behavior remains unchanged for OpenAI keys.

## Acceptance Criteria
1. A user can save keys with provider metadata in Profile.
2. Selecting a non-OpenAI key routes calls through provider-specific `base_url`.
3. OpenAI keys still use current model dropdown; non-OpenAI keys use free-text model.
4. Existing stored keys continue to work without edits.
5. Unit/integration/E2E suites pass with updated coverage.

## Assumptions and Defaults
1. Provider support in this scope is `openai`, `openrouter`, `custom`.
2. OpenRouter endpoint is fixed and not user-editable.
3. Non-OpenAI model names are provider-specific strings entered by user.
4. OpenRouter-specific optional headers are out of scope for this iteration.
