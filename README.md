# OmniShelf 1.3.9 — Account Recovery Preview

This feature branch extends the 1.3.8 single-page frontend and FastAPI persistence foundation with email verification and password recovery. It is deployed to an isolated Free Render staging service for controlled acceptance only; it is not a public release. The existing 1.3.8 HTTPS preview and archived 1.0.0 service remain unchanged.

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

### Isolated 1.3.9 staging service — current verified status

The separate Free Render service is live at https://omnishelf-1-3-9-email-recovery-staging.onrender.com and deploys from `feature/1.3.9-email-verification-password-reset`. It is isolated from the 1.3.8 preview and archived 1.0.0 service.

- The private `DATABASE_URL` was entered directly in Render for Neon project `omnishelf-preview` → branch `omnishelf-1-3-9-email-recovery-staging` → database `neondb`; no connection URI is stored in source or chat.
- The hosted target guard verified the intended non-secret host and database name before migrations.
- The isolated database now reports Alembic revision `003_email_verification_and_reset`. This migration has **not** been applied to Neon `main`.
- Render's native health check is configured to `/healthz`; logs show HTTP 200 responses and a successful deployment.
- Live OIDC-protected acceptance passed on real staging PostgreSQL: secure cookie attributes; public signup remains closed; concurrent initial cloud saves serialize; stale revisions cannot overwrite current data; snapshot persistence across logout/sign-in; two-account isolation; export omits password/session secrets; and password-confirmed account deletion revokes sessions. All temporary accounts were deleted; a read-only query confirms zero remaining synthetic test accounts.
- The OIDC-only staging bootstrap was switched off in Render, and the close-down redeploy completed successfully. The `/healthz` endpoint continued returning HTTP 200. Its default remains `false` in the source blueprint.
- Public registration remains disabled. SMTP acceptance remains disabled, no real email has been sent, and the existing 1.3.8 and 1.0.0 services remain unchanged.

### Next gate — SMTP provider and real-mailbox acceptance

Recommended low-friction provider: [Resend](https://resend.com/), which supports SMTP and currently lists a free tier of 3,000 emails/month, with a 100/day limit. Check its [current pricing](https://resend.com/pricing) before relying on those limits. A verified sending domain is required for normal use; don't purchase a domain or upgrade to a paid plan without deciding that separately. See [Resend's SMTP setup](https://resend.com/changelog/smtp-service).

For a Resend SMTP integration compatible with OmniShelf's STARTTLS configuration, use:

- `SMTP_HOST=smtp.resend.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME=resend`
- `SMTP_PASSWORD`: a Resend API key with sending permission (private secret)
- `SMTP_FROM_EMAIL`: a sender address under a verified domain
- `SMTP_FROM_NAME=OmniShelf`
- `SMTP_STARTTLS=true`

Keep `EMAIL_VERIFICATION_REQUIRED=true`, `COOKIE_SECURE=true`, `REGISTRATION_ENABLED=false`, and `OMNISHELF_SMTP_ACCEPTANCE_ENABLED=false` outside the explicit one-off test. `PUBLIC_APP_ORIGIN` must remain the exact HTTPS staging origin.

The non-secret connection values (`SMTP_HOST=smtp.resend.com`, `SMTP_PORT=587`, `SMTP_USERNAME=resend`, `SMTP_STARTTLS=true`, `SMTP_FROM_NAME=OmniShelf`) have already been set on the isolated staging service. You still need to create/access the provider account, verify a sending domain you control, create a sending API key, and privately add `SMTP_PASSWORD` and `SMTP_FROM_EMAIL` through Render's Environment settings. Never send the API key in chat or commit it to Git. Once the sender domain is verified and credentials are saved, run the configuration preflight and then perform exactly one opt-in acceptance message to a mailbox you control. Immediately switch the acceptance flag back off and verify the message in Inbox/Spam. Only then proceed to verification, resend, reset, token-replay, generic-response, and session-revocation checks. Do not enable public registration during staging acceptance.

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

## Explicit SMTP delivery acceptance

When credentials have been added to the intended private service environment, use a dedicated test mailbox and run this one-off command from an authorized shell. The opt-in flag is deliberately required so the command cannot accidentally send during app startup or normal CI:

```bash
OMNISHELF_SMTP_ACCEPTANCE_ENABLED=true \
SMTP_TEST_RECIPIENT=your-controlled-mailbox@example.com \
python -m backend.smtp_acceptance
```

The command re-checks the required hosted configuration, validates the recipient, connects with certificate-validated STARTTLS, authenticates, and sends one harmless test message to the explicitly specified recipient. It never includes an account token/password, and it does not print credential values or SMTP exception details. It reports only whether the SMTP server accepted the message; **open the dedicated mailbox** (including spam/quarantine) to confirm delivery. Do not leave the opt-in flag enabled persistently and do not run the command until the recipient is confirmed to be a mailbox you control.

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
