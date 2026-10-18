# OmniShelf 1.3.9 — Account Recovery Preview

This feature branch extends the 1.3.8 single-page frontend and FastAPI persistence foundation with email verification and password recovery. It is not deployed. The existing 1.3.8 HTTPS preview remains unchanged until review, database-target reconciliation and email-provider configuration are complete.

## What is included

- Single-file OmniShelf frontend at `index.html`
- FastAPI account/session and revisioned cloud snapshot API under `backend/`
- Alembic schema migrations
- Docker deployment entry point
- Local-first library, profile, favourites, reviews, work relationships, catalogue lookup and appearance settings

## Deploy locally

Requires Python 3.12+ and PostgreSQL for production-style testing.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
export DATABASE_URL='sqlite:///./omnishelf-dev.db'
export COOKIE_SECURE=false
export REGISTRATION_ENABLED=true
export EMAIL_VERIFICATION_REQUIRED=false # localhost-only shortcut; never use this on a hosted service
alembic -c backend/alembic.ini upgrade head
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`. The example keeps email verification disabled only to make private local development work without an SMTP sender. Never use that shortcut on a hosted service; the backend fails startup if Render registration is enabled without verification.

## Render preview

Use a Docker web service with this branch and root `Dockerfile`, in the same region as the managed Postgres instance. Set `DATABASE_URL` to Render's **internal** database URL and configure:

- `COOKIE_SECURE=true`
- `REGISTRATION_ENABLED=false` until email delivery, account recovery, abuse protections, backups and independent review are complete
- `EMAIL_VERIFICATION_REQUIRED=true`
- `PUBLIC_APP_ORIGIN=https://your-real-app-host`
- `OMNISHELF_EXPECTED_DATABASE_HOST` — the exact hostname of the approved database endpoint
- `OMNISHELF_EXPECTED_DATABASE_NAME` — the exact database name for the approved target
- `SESSION_TTL_SECONDS=2592000`
- `MAX_STATE_BYTES=20971520`

The container runs Alembic migrations before starting Uvicorn. `/healthz` verifies DB connectivity. Do not expose DB credentials in logs, client code, commits or screenshots.

### Hosted database target guard

Before a hosted container applies **any** Alembic migration, it now runs `python -m backend.database_target_preflight`. In Render, set `OMNISHELF_EXPECTED_DATABASE_HOST` and `OMNISHELF_EXPECTED_DATABASE_NAME` in the service's private environment settings, using values independently confirmed for the intended Neon branch/database. The guard compares those values to the non-secret hostname/database name in `DATABASE_URL`, then performs read-only queries for `current_database()` and the applied Alembic revision. If the expected values are missing, do not match, or the identity query fails, startup stops **before migrations run**.

On success it reports only the verified host, database name, and current Alembic revision—not the connection URL, username, or password. Never paste `DATABASE_URL` into chat or logs. The check does not change schema or data. Local development skips this hosted-only guard. This safeguard is only as trustworthy as the independently confirmed expected target; do not copy expected values from an unverified connection string.

## Account email setup

The API now supports one-time email verification, resending a verification message, and password-reset requests and confirmation. Before enabling hosted registration, configure these environment variables in the service's secret settings:

- `SMTP_HOST`, `SMTP_PORT` (normally 587), `SMTP_USERNAME`, `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`, optional `SMTP_FROM_NAME`, and `SMTP_STARTTLS=true`
- `EMAIL_VERIFICATION_REQUIRED=true` and the exact HTTPS `PUBLIC_APP_ORIGIN`

Email verification links expire after 24 hours by default; password-reset links expire after 30 minutes. Tokens are random, single-use, and stored only as hashes. Password recovery revokes all active sessions. SMTP authentication is refused when STARTTLS is disabled. If the sender is missing, signup/recovery endpoints fail closed with HTTP 503; public registration remains disabled in the deployed preview. Existing accounts are grandfathered as verified by migration 003.

## Hosted email preflight (configuration only)

After adding the intended hosted environment variables in the service's private settings, run this command from the deployed code or a secure shell attached to that service:

```bash
python -m backend.config_preflight
```

The preflight checks that required SMTP settings are present, the SMTP port is valid, STARTTLS/email verification/Secure cookies are enabled, public registration remains disabled, and `PUBLIC_APP_ORIGIN` is an HTTPS origin. It prints only setting names and validation messages, never configured values. It **does not** contact the SMTP server, prove sender-domain ownership, or verify real mailbox delivery; the acceptance checklist below remains required.

## SMTP acceptance checklist

Do not put SMTP credentials in GitHub source files, workflow YAML, issue comments, or screenshots. Add them only to the intended Render service's private environment settings. Then verify delivery against a dedicated test mailbox before any production cutover:

1. Confirm `/healthz` succeeds and ordinary public registration is still disabled.
2. Send a verification email from a controlled test account; open its HTTPS link once, then confirm replay is rejected.
3. Request a password reset, use the link once, sign in with the new password, and confirm the prior session is revoked.
4. Confirm the verification/reset-request endpoints return the same generic response for an unknown address and for a known address whose SMTP delivery fails.
5. After deployment, verify the service's configured database target and applied Alembic revision using read-only checks before treating migration 003 as hosted.

The CI suite uses a mocked SMTP transport to check that STARTTLS with certificate validation and configured authentication are used; this is not a substitute for a real-mailbox delivery test.

## Known scope limits

This remains a controlled preview, not a public launch. A real SMTP provider still needs to be configured and end-to-end delivery verified; recurring backup scheduling/retention, additional abuse controls, independent security review, and provider/licensing review remain open. Media-upload storage and shared cross-user community data are also not implemented.
