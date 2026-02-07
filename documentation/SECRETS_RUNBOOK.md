# Secrets Runbook

This runbook defines where environment and credential configuration should live, so values are not lost and are easy to rotate safely.

## Goals
- Keep all real secrets out of git.
- Have one canonical location for each environment.
- Make production/staging setup reproducible.

## Canonical Storage
1. Password manager (source of truth):
- Store all real values in a shared vault entry named `AI Assistant Competition` with sections `production`, `staging`, and `local`.
- Keep DB URLs, API keys, and service-account JSON fields there.

2. Hosted secret managers:
- Streamlit deployment: set secrets in Streamlit Secrets UI.
- CI/CD (GitHub Actions): set repository/environment secrets.

3. Local machine convenience (optional):
- Use a local, gitignored env file (`.env`, `.env.local`) for day-to-day commands.
- Use `streamlit/.streamlit/secrets.toml` locally only; do not commit it.

## Required Variables and Fields
- `DATABASE_URL`: app runtime DB URL.
- `PRODUCTION_DATABASE_URL`: Makefile production DB target.
- `STAGING_DATABASE_URL`: Makefile staging DB target.
- `ADMIN_EMAIL`: admin user email for minimal production/staging seed.
- `ADMIN_PASSWORD_HASH`: SHA-256 hash for admin password used by minimal seed.
- `API_KEY_ENCRYPTION_KEY`: Fernet key used to encrypt user API keys.
- `E2E_INSTRUCTOR_EMAIL`, `E2E_INSTRUCTOR_PASSWORD`, `E2E_OPENAI_API_KEY` (if E2E is used).

`streamlit/.streamlit/secrets.toml` sections used by app:
- `[database].url` (production app DB by default)
- `[database_staging].url` (used by Makefile staging targets)
- `[drive]` Google service-account fields and `folder_id`
- `[mail].email`, `[mail].api_key`
- `[app].link`

See `streamlit/.streamlit/secrets.example.toml` and `.env.example` for templates.

## Setup Procedure (New Machine)
1. Pull secret values from password manager.
2. Create local env file from `.env.example` and fill only local values.
3. Create `streamlit/.streamlit/secrets.toml` from `streamlit/.streamlit/secrets.example.toml`.
4. If you need to reset production/staging DBs, prepare admin seed values:
- `ADMIN_EMAIL` (real admin email)
- `ADMIN_PASSWORD_HASH` (generate with `printf '%s' '<password>' | shasum -a 256 | awk '{print $1}'`)
4. Verify connectivity:
- `make test-production-db-connection`
- `make test-staging-db-connection`

## Rotation Procedure
1. Rotate credential at provider first (Supabase/OpenAI/Google/mail).
2. Update password manager entry.
3. Update hosted secret managers (Streamlit, CI).
4. Update local env/secrets files.
5. Validate:
- `make test-production-db-connection`
- `make test-staging-db-connection`
6. Announce rotation date and owner in team channel.

## Backup and Recovery
- Password manager is the long-term backup for all secret values.
- Keep at least two maintainers with vault access.
- If a maintainer leaves, rotate all production and staging credentials.

## Guardrails
- Never paste real credentials in issues/PRs/chat logs.
- Never commit `streamlit/.streamlit/secrets.toml` or populated `.env` files.
- Treat production DB as restricted: no destructive resets without explicit approval.
