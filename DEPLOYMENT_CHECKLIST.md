# OmniShelf controlled preview checklist

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
