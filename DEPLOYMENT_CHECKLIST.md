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

### Still blocked before deploying 1.3.9
- [ ] Confirm the Render workspace and independently identify the intended Neon endpoint hostname and database name; do not infer them from an unverified connection string.
- [ ] Add `OMNISHELF_EXPECTED_DATABASE_HOST` and `OMNISHELF_EXPECTED_DATABASE_NAME` privately to the **intended 1.3.9 staging service**. Do not change the live 1.3.8 service as a shortcut.
- [ ] Configure SMTP host, port, username, password, sender, HTTPS `PUBLIC_APP_ORIGIN`, and verification/Secure-cookie flags in that isolated service's private settings.
- [ ] Choose a mailbox under the operator's control, then explicitly run `python -m backend.smtp_acceptance` with `OMNISHELF_SMTP_ACCEPTANCE_ENABLED=true` and `SMTP_TEST_RECIPIENT` configured only for that one-off acceptance check. Turn the opt-in flag off immediately afterwards and verify the mailbox itself.
- [ ] Confirm the target preflight identifies the intended endpoint/database and current migration revision before approving migration 003.
- [ ] Complete live verification/resend/reset/replay/session-revocation checks on staging with controlled accounts, then review screenshots.
- [ ] Complete backup/restore and retention planning, independent security review, and provider/licensing review before public launch.

**Safety status:** this is a feature-branch checklist only. No hosted database was migrated, no live Render service was changed, and public registration remains disabled.

## Isolated Neon/Render staging target — preparation
- [x] Created dedicated Neon child branch `omnishelf-1-3-9-email-recovery-staging` (`br-summer-heart-aop6p1em`) from isolated `auth-staging-2026-10-16`, not Neon `main`.
- [x] Read-only query confirmed the new branch's `neondb` database starts at `002_shared_auth_rate_limits`; migration 003 has not been applied yet.
- [x] Added `render.staging.yaml` for a separate Free Render service on the 1.3.9 feature branch. It pins the expected non-secret database hostname/name, keeps registration closed, requires email verification and Secure cookies, and keeps SMTP acceptance disabled.
- [x] Blueprint marks `DATABASE_URL` as `sync: false`; no database URI or password is committed to source.
- [ ] Create the staging Render Blueprint from the Render dashboard, selecting custom blueprint path `render.staging.yaml`, then enter the new Neon branch's pooled `neondb` URI directly into Render's initial private secret prompt. Do not paste the URL into chat or a source file.
- [ ] Confirm staging startup logs show the expected hostname/database and revision 002 before migration 003; verify migration 003 completes on this child branch only. If target check blocks startup, do not change existing service URLs.
- [ ] Configure SMTP privately and perform the opt-in test against a controlled mailbox. No real SMTP message has been sent yet.

**Current status:** the Neon branch and source blueprint are prepared; the Render staging service has not yet been created. The protected connection URI needs to be entered directly in Render's dashboard to avoid putting a privileged secret in the code workflow.

## Render 1.3.9 staging service — current runtime result
- [x] Created Free Render web service `omnishelf-1-3-9-email-recovery-staging`: https://omnishelf-1-3-9-email-recovery-staging.onrender.com
- [x] The Docker image built successfully from the 1.3.9 feature branch; source commit: `575fedb61e68d821f4b09c5aa2229771bd68c812`.
- [x] The first start exited closed with the diagnostic `Missing required setting: DATABASE_URL`. The preflight stopped startup before Alembic, so no database migration ran. This is intentional until the secret is supplied directly through Render's private dashboard.
- [x] Read-only Neon check after that deployment failure still reports `neondb` at `002_shared_auth_rate_limits`; migration 003 remains unapplied to the isolated staging branch.
- [ ] In Render Dashboard → service → Environment, add `DATABASE_URL` by copying the pooled URI for Neon project `omnishelf-preview`, branch `omnishelf-1-3-9-email-recovery-staging`, database `neondb`. Paste directly into Render; do not send it in chat or source control. Saving should restart/redeploy the service.
- [ ] After startup, verify logs show the expected target hostname, `database=neondb`, and revision 002 before Alembic then applies migration 003. Read-only Neon query must show `003_email_verification_and_reset` afterwards.
- [ ] Configure SMTP credentials privately and run the explicit one-off acceptance command only with a mailbox under the operator's control. SMTP acceptance remains disabled and no real email has been sent.
- [ ] Set Render's native health check path to `/healthz` in the service settings; the create-service API did not expose that field, although the source blueprint specifies it.

**No impact:** live 1.3.8 preview and the archived 1.0.0 service have not been modified. Public registration remains disabled.

