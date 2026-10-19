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

## 1.3.9 email and database release gates (feature branch only)

### CI/source validation
- [x] Email-verification and password-reset endpoints use one-time hashed tokens, expiries, rate limits, generic recovery responses, and revoke sessions after password reset.
- [x] SMTP sending requires STARTTLS with certificate verification; delivery failure does not disclose whether the email belongs to an account.
- [x] Hosted email configuration preflight reports missing/unsafe settings without printing values.
- [x] Hosted database target preflight runs **before** Alembic migrations and blocks startup if the independently expected host/database is missing or does not match; successful target inspection is read-only.
- [x] Explicit SMTP acceptance command requires an opt-in flag and a dedicated test-recipient setting; CI uses a mocked SMTP client and sends no real email.
- [x] Latest full 1.3.9 code CI run before this checklist/environment documentation update: [39155450165](https://github.com/Reisquin/Omnishelf/actions/runs/39155450165) (five jobs passed, including PostgreSQL integration and visual previews).

### Current 1.3.9 release gates

- [x] Confirm the intended Render workspace and isolate the Neon child branch `omnishelf-1-3-9-email-recovery-staging`, database `neondb`.
- [x] Add the expected database host/name guard and private `DATABASE_URL` to the isolated Render staging service.
- [x] Confirm the hosted target guard identified the intended endpoint and database before migration.
- [x] Apply migration `003_email_verification_and_reset` only to the isolated staging branch; read-only Neon query confirms the new Alembic revision.
- [x] Set Render's native health-check path to `/healthz`; latest logs show HTTP 200 health checks and a successful deploy.
- [ ] Configure SMTP host, port, sending username, password/API key, verified sender address, and HTTPS origin in the isolated service's private settings. Never store provider credentials in Git or chat.
- [ ] Run the hosted email configuration preflight without printing values.
- [ ] Run the opt-in SMTP delivery acceptance test exactly once to a confirmed mailbox under the operator's control; disable the opt-in flag immediately afterwards and verify actual inbox/spam delivery.
- [x] Live OIDC-protected staging acceptance passed: Secure/HttpOnly/SameSite session cookies; public registration denied; concurrent first writes serialize to one success/one conflict; stale revision cannot overwrite saved state; snapshot persists across logout/sign-in; two-account data is isolated; export excludes password/session secrets; account deletion requires the correct password and revokes all sessions. [Run 39318642200](https://github.com/Reisquin/Omnishelf/actions/runs/39318642200).
- [x] Acceptance cleanup verified with a read-only Neon query: zero synthetic staging test accounts remain. The OIDC bootstrap switch has been changed back to `false`; Render redeployment is closing those test-only routes.
- [ ] Verify email verification/resend/password-reset flows, one-time token replay prevention, generic responses on unknown-address/SMTP-failure cases, and post-reset session revocation after real SMTP delivery is configured.
- [ ] Complete backup/restore and retention planning, independent security review, and provider/licensing review before public launch.

**Current safety status:** the isolated 1.3.9 staging service is live and migrated, but this is not a public release. Public registration remains disabled, SMTP acceptance remains off, and no real SMTP email has been sent. The existing 1.3.8 preview and archived 1.0.0 service remain unchanged.

## Isolated Neon/Render staging target — verified deployment

- [x] Created Neon project `omnishelf-preview` with dedicated child branch `omnishelf-1-3-9-email-recovery-staging` (`br-summer-heart-aop6p1em`), not Neon `main`.
- [x] Created Free Render web service `omnishelf-1-3-9-email-recovery-staging` (`srv-dbaib6eq1p3s73bpmsig`) on `feature/1.3.9-email-verification-password-reset`: https://omnishelf-1-3-9-email-recovery-staging.onrender.com
- [x] Added the pooled Neon connection URI directly in Render's private environment. The URI/password do not appear in Git, logs, or chat.
- [x] The pre-migration target check confirmed the expected hostname and `neondb`; only then did Alembic upgrade `002_shared_auth_rate_limits` to `003_email_verification_and_reset`.
- [x] Independent read-only Neon query confirms `neondb` at `003_email_verification_and_reset`; migration 003 was applied to the isolated child branch only.
- [x] Render native health-check setting is `/healthz`; the service is live and Render logs show `GET /healthz` returning HTTP 200.
- [x] Staging blueprint keeps the free plan, registration disabled, email verification required, Secure cookies enabled, and SMTP acceptance disabled by default.
- [ ] SMTP provider account/API key and verified sender address are still required. Non-secret Resend SMTP settings (host, port 587, username `resend`, STARTTLS, and sender name) are configured. Add `SMTP_PASSWORD` (sending API key) and `SMTP_FROM_EMAIL` privately in Render. Use a domain you control; do not purchase a domain or upgrade a provider plan without deciding that separately.
- [ ] Run configuration preflight and explicit opt-in single-message SMTP acceptance to a mailbox under the operator's control; disable the acceptance flag immediately afterwards and verify actual delivery.
- [ ] Complete controlled account-flow acceptance for verification/resend/reset/token replay/session revocation after mail delivery works.

**No impact:** live 1.3.8 preview and the archived 1.0.0 service have not been modified. Public registration remains disabled until the remaining review and operations gates are complete.
