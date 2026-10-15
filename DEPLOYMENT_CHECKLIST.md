# OmniShelf controlled preview checklist

## Pre-deployment checks (CI)
- [x] Free-first Render blueprint contains exactly one Free web service, no Render database, a dashboard-only DATABASE_URL secret, and registration disabled (CI run 38825891605).
- [x] API tests pass against an isolated SQLite test database, including account snapshot isolation, stale revisions, HTTPS session-cookie flags, security headers and request-body limits.
- [x] Alembic migrations apply successfully to a fresh SQLite database.
- [x] Playwright captures current desktop and mobile screenshots.
- [x] Browser run has no uncaught JavaScript errors.
- [x] Mobile page has no horizontal page overflow.
- [x] Profile Top 25 favourites render in the approved category order.
- [ ] Exercise database locks and concurrent first-time snapshot writes against PostgreSQL; SQLite CI is not a substitute for a production-dialect check.
- [ ] Run the live /healthz, account-disabled and cloud snapshot acceptance checks after the isolated PostgreSQL-backed service is deployed.

## Free-first deployment option
- Use `render.free.yaml` with a Neon Free PostgreSQL project. Do not use the default paid `render.yaml` for this path.
- Keep Neon’s pooled connection string only in Render’s `DATABASE_URL` secret; never commit it or paste it into chat.
- Do not add paid plans or accept billing prompts. Render Free is for controlled preview only; use a persistent database provider because Render Free Postgres expires after 30 days.

## Before service creation
- [x] Put 1.3.8 frontend and API foundation on an isolated deployment branch.
- [x] Keep the existing 1.0.0 Render service and `main` branch untouched.
- [x] Use same-origin frontend/API routes so session cookies remain first-party.
- [x] Keep public registration disabled by default.
- [ ] Provision managed PostgreSQL once billing is available.
- [ ] Create a separate Docker web service on this branch.

## Environment
- `DATABASE_URL`: Render internal PostgreSQL URL; secret, never commit it.
- `COOKIE_SECURE=true`
- `REGISTRATION_ENABLED=false`
- `SESSION_TTL_SECONDS=2592000`
- `MAX_STATE_BYTES=20971520`

## Acceptance tests after deployment
- [ ] `GET /healthz` returns 200 with database status OK.
- [ ] Schema migration completed successfully.
- [ ] Login/session cookies are Secure, HttpOnly, and SameSite=Lax.
- [ ] Registration remains disabled in the controlled preview.
- [ ] Snapshot write/read survives application redeploys and user sign-out/sign-in.
- [ ] Stale snapshot revision returns 409 without overwriting newer data.
- [ ] Two test accounts cannot access each other's snapshots.
- [ ] Current frontend loads without JavaScript exceptions on desktop and mobile.
- [ ] Screenshots from this exact deployed commit are captured.

## Before public launch
- [ ] Email verification, password recovery and account deletion/export.
- [ ] Shared rate limiting and abuse prevention.
- [ ] Automated database backups and a restore drill.
- [ ] Independent security review and provider/licensing review.
- [ ] Enable registration only after all preceding items are complete.
