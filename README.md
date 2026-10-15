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
alembic -c backend/alembic.ini upgrade head
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`. Local registration is enabled by the environment above; do not use that setting on a public preview without an abuse-control and account-recovery plan.

## Render preview

Use a Docker web service with this branch and root `Dockerfile`, in the same region as the managed Postgres instance. Set `DATABASE_URL` to Render's **internal** database URL and configure:

- `COOKIE_SECURE=true`
- `REGISTRATION_ENABLED=false` until account verification, recovery, and abuse protections are ready
- `SESSION_TTL_SECONDS=2592000`
- `MAX_STATE_BYTES=20971520`

The container runs Alembic migrations before starting Uvicorn. `/healthz` verifies DB connectivity. Do not expose DB credentials in logs, client code, commits or screenshots.

## Known scope limits

This backend stores a private, revisioned account snapshot. Email verification/password recovery, account deletion, media-upload storage, shared social data, provider licensing acceptance and full production security review are still required before public registration or a public launch.
