# OmniShelf controlled preview checklist

## Pre-deployment checks (CI)
- [x] Free-first Render blueprint contains exactly one Free web service, no Render database, a dashboard-only DATABASE_URL secret, and registration disabled (CI run 38825891605).
- [x] API tests pass against isolated SQLite, including session-cookie flags, account snapshot isolation, stale revisions, safety headers and request size limits.
- [x] Alembic migrations apply to a fresh SQLite database.
- [x] Playwright checks desktop/mobile, favourite category order, JavaScript exceptions and mobile overflow.
- [x] Live smoke workflow checks health, PostgreSQL, HTTPS headers, disabled registration, root route, desktop/mobile rendering and captures real screenshots (run 38851867077).
- [x] PostgreSQL 16 integration suite applies Alembic migrations and verifies stale-revision conflicts, concurrent first-time snapshot writes, session persistence after re-login, and per-account isolation (run 38851867171). Tests use an ephemeral CI database, not the hosted Neon database.

## Deployment configuration
- [x] Isolated branch `deploy/1.3.8-https-preview`; existing `main` and 1.0.0 service unchanged.
- [x] Free Render Docker web service `omnishelf-1-3-8-free` created in confirmed `My Workspace`.
- [x] Neon Free PostgreSQL project in Singapore created and pooled URI stored directly in Render secret environment.
- [x] No Render-hosted Postgres database created; paid blueprint preserved only as optional future upgrade.
- [x] `COOKIE_SECURE=true` and `REGISTRATION_ENABLED=false`.
- [x] Initial deploy live; PostgreSQL migration `001_initial_backend` completed and database tables verified with Neon.
- [ ] Native Render healthCheckPath setting: API creation tool did not expose this setting. `render.free.yaml` sets `/healthz`; external live smoke workflow already checks this endpoint.
- [x] No paid resource intentionally created.

## Environment
- `DATABASE_URL`: Neon pooled PostgreSQL URI stored only as a Render dashboard secret. Never commit or share it.
- `COOKIE_SECURE=true`
- `REGISTRATION_ENABLED=false`
- `SESSION_TTL_SECONDS=2592000`
- `MAX_STATE_BYTES=20971520`

## Live acceptance checks
- [x] `GET /healthz` returns HTTP 200, PostgreSQL status OK, version 1.3.8.
- [x] Neon Alembic migration completed; `users`, `sessions`, `state_snapshots`, and `alembic_version` exist.
- [x] HTTPS HSTS and `X-Content-Type-Options: nosniff` confirmed.
- [x] `/api/auth/me` returns 200 and `Cache-Control: no-store`.
- [x] Registration remains disabled and returns HTTP 403.
- [ ] Successful live login's Set-Cookie attributes (Secure, HttpOnly, SameSite=Lax); source/unit tests verify these flags, but no authenticated test session has been created while registration is closed.
- [ ] Hosted Neon snapshot write/read survives sign-out/sign-in and an app redeploy (automated PostgreSQL CI test passes; hosted authenticated test still pending).
- [ ] Hosted Neon stale snapshot revision returns 409 without overwriting newer data (automated PostgreSQL CI test passes; hosted authenticated test still pending).
- [ ] Hosted Neon two-account isolation test (automated PostgreSQL CI test passes; hosted authenticated test still pending).
- [x] Live frontend loads without uncaught JavaScript errors on desktop and mobile.
- [x] Full-page screenshots captured from live service: https://github.com/Reisquin/Omnishelf/actions/runs/38851867077
- [x] Deployment uses the Render Free plan and Neon Free plan. Neon currently lists 100 CU-hours, 0.5 GB storage, and 5 GB public network transfer per project/month; usage must be reviewed periodically.

## Before public launch
- [ ] Email verification, password recovery and account deletion/export.
- [ ] Shared rate limiting and abuse prevention across instances.
- [ ] Automated database backup and restore drill.
- [ ] Independent security and provider/licensing review.
- [ ] Enable registration only after all preceding items are complete.
