# OmniShelf 1.3.8 — Deployment Preview

This branch contains the 1.3.8 single-page frontend and FastAPI persistence foundation. It is intended for a controlled HTTPS preview, not open public registration.

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
- `SESSION_TTL_SECONDS=2592000`
- `MAX_STATE_BYTES=20971520`

The container runs Alembic migrations before starting Uvicorn. `/healthz` verifies DB connectivity. Do not expose DB credentials in logs, client code, commits or screenshots.

## Account email setup

The API now supports one-time email verification, resending a verification message, and password-reset requests and confirmation. Before enabling hosted registration, configure these environment variables in the service's secret settings:

- `SMTP_HOST`, `SMTP_PORT` (normally 587), `SMTP_USERNAME`, `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`, optional `SMTP_FROM_NAME`, and `SMTP_STARTTLS=true`
- `EMAIL_VERIFICATION_REQUIRED=true` and the exact HTTPS `PUBLIC_APP_ORIGIN`

Email verification links expire after 24 hours by default; password-reset links expire after 30 minutes. Tokens are random, single-use, and stored only as hashes. Password recovery revokes all active sessions. SMTP authentication is refused when STARTTLS is disabled. If the sender is missing, signup/recovery endpoints fail closed with HTTP 503; public registration remains disabled in the deployed preview. Existing accounts are grandfathered as verified by migration 003.

## Known scope limits

This remains a controlled preview, not a public launch. A real SMTP provider still needs to be configured and end-to-end delivery verified; recurring backup scheduling/retention, additional abuse controls, independent security review, and provider/licensing review remain open. Media-upload storage and shared cross-user community data are also not implemented.
