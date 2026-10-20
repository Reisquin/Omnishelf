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
- Public registration remains disabled. The one-off email acceptance switches are disabled by default. Existing 1.3.8 and 1.0.0 services remain unchanged.

### Next gate — Resend HTTPS sandbox acceptance

Recommended provider: [Resend](https://resend.com/). Render's Free web services block outbound SMTP ports, so OmniShelf now uses Resend's HTTPS API on port 443 when hosted on Render Free. Resend's sandbox sender supports a limited domain-free test; normal email delivery to arbitrary users still requires a sender domain verified by Resend. See [Resend's email API docs](https://resend.com/docs/api-reference/emails/send-email).

For the Render Free staging deployment, use the HTTPS API settings:

- `EMAIL_DELIVERY_PROVIDER=resend_api`
- `SMTP_PASSWORD`: the private Resend sending API key (kept in Render's Environment settings; `RESEND_API_KEY` is also supported)
- `SMTP_FROM_EMAIL=onboarding@resend.dev` for the restricted sandbox
- `SMTP_FROM_NAME=OmniShelf`

The app retains SMTP support for local development and hosted plans that permit it; Resend SMTP on port 587 timed out on Render Free.

Keep `EMAIL_VERIFICATION_REQUIRED=true`, `COOKIE_SECURE=true`, `REGISTRATION_ENABLED=false`, and `OMNISHELF_SMTP_ACCEPTANCE_ENABLED=false` outside the explicit one-off test. `PUBLIC_APP_ORIGIN` must remain the exact HTTPS staging origin. The HTTPS API key is read only at runtime and is never printed.

The isolated Render service has the sandbox sender `onboarding@resend.dev` configured. Never send the API key in chat or commit it to Git. The latest attempted SMTP test timed out because Render Free blocks SMTP ports, so the transport is being switched to Resend's HTTPS API; the HTTPS sandbox test still needs to pass. It targets `delivered@resend.dev`, a simulated-delivery address rather than a real inbox, and sends no account token. The API-key value is not read back or printed during verification. Keep the acceptance switches off after the one-off check. Before any real public verification/reset emails are enabled, verify a sender domain you control and test actual inbox delivery. Do not enable public registration during staging acceptance.

## Account email setup

The API now supports one-time email verification, resending a verification message, and password-reset requests and confirmation. Before enabling hosted registration, configure the environment settings for the chosen transport in the service's private settings:

- For Resend on Render Free: `EMAIL_DELIVERY_PROVIDER=resend_api`, `SMTP_PASSWORD` (or `RESEND_API_KEY`) as the private API key, and `SMTP_FROM_EMAIL`/`SMTP_FROM_NAME`.
- For SMTP on a service that permits outbound SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, optional `SMTP_FROM_NAME`, and `SMTP_STARTTLS=true`.
- `EMAIL_VERIFICATION_REQUIRED=true` and the exact HTTPS `PUBLIC_APP_ORIGIN`

Email verification links expire after 24 hours by default; password-reset links expire after 30 minutes. Tokens are random, single-use, and stored only as hashes. Password recovery revokes all active sessions. SMTP authentication is refused when STARTTLS is disabled. On Render Free, Resend delivery uses HTTPS rather than SMTP. If the selected provider or sender is missing, signup/recovery endpoints fail closed with HTTP 503; public registration remains disabled in the deployed preview. Existing accounts are grandfathered as verified by migration 003.

## Hosted email preflight (configuration only)

After adding the intended hosted environment variables in the service's private settings, run this command from the deployed code or a secure shell attached to that service:

```bash
python -m backend.config_preflight
```

The preflight checks the selected provider's required settings, HTTPS origin, email-verification/Secure-cookie flags, and closed public registration. It prints setting names and validation messages, never configured values. It **does not** contact the email provider, prove sender-domain ownership, or verify real mailbox delivery; the acceptance checklist below remains required.

## Explicit email delivery acceptance

When credentials have been added to the intended private service environment, use a dedicated test mailbox and run this one-off command from an authorized shell. The opt-in flag is deliberately required so the command cannot accidentally send during app startup or normal CI:

```bash
OMNISHELF_SMTP_ACCEPTANCE_ENABLED=true \
SMTP_TEST_RECIPIENT=delivered@resend.dev \
EMAIL_DELIVERY_PROVIDER=resend_api \
python -m backend.smtp_acceptance
```

In Resend API mode, the command re-checks the required configuration, sends one harmless test message over HTTPS, and reports only provider acceptance or a sanitized status code. It never includes an account token/password and never prints key values or provider response bodies. With `delivered@resend.dev`, the response is simulated and is not a real inbox delivery. For a true mailbox test, use an address you control after a verified sender domain is configured. Do not leave the opt-in flag enabled persistently.

## Email acceptance checklist

Do not put SMTP or Resend API credentials in GitHub source files, workflow YAML, issue comments, or screenshots. Add them only to the intended Render service's private environment settings. Verify the domain-free sandbox API request first, then verify actual inbox delivery to a controlled mailbox once a sender domain is available:

1. Confirm `/healthz` succeeds and ordinary public registration is still disabled.
2. Send a verification email from a controlled test account; open its HTTPS link once, then confirm replay is rejected.
3. Request a password reset, use the link once, sign in with the new password, and confirm the prior session is revoked.
4. Confirm the verification/reset-request endpoints return the same generic response for an unknown address and for a known address whose provider delivery fails.
5. After deployment, verify the service's configured database target and applied Alembic revision using read-only checks before treating migration 003 as hosted.

The CI suite checks both the Resend HTTPS API request shape and the optional SMTP STARTTLS path using mocks; this is not a substitute for provider acceptance and actual inbox delivery.

## Known scope limits

This remains a controlled preview, not a public launch. The Resend HTTPS sandbox check and real sender-domain/inbox delivery acceptance remain separate gates; recurring backup scheduling/retention, additional abuse controls, independent security review, and provider/licensing review remain open. Media-upload storage and shared cross-user community data are also not implemented.
