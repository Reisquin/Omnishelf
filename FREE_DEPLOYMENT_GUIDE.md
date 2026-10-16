# OmniShelf 1.3.8 — Free-first preview deployment

## Current deployment

- **Live app + API:** https://omnishelf-1-3-8-free.onrender.com
- **Render web service:** `omnishelf-1-3-8-free`, Free plan, Singapore.
- **Database:** Neon Free PostgreSQL project `omnishelf-preview`, Singapore (`aws-ap-southeast-1`).
- **Registration:** `REGISTRATION_ENABLED=false`; new accounts remain blocked during controlled testing.
- **Existing launch:** The original 1.0.0 Render service and `main` branch are untouched.
- **Optional paid upgrade:** The original `render.yaml` is preserved for future use only. The running preview uses the Free service configuration.

## Verified live checks

The deployed smoke-test workflow succeeded on 2026-10-16:

- `GET /healthz` returned HTTP 200 with PostgreSQL status `ok` and version `1.3.8`.
- Alembic applied migration `001_initial_backend`; Neon confirms `users`, `sessions`, `state_snapshots` and `alembic_version` tables exist.
- HTTPS HSTS and `X-Content-Type-Options: nosniff` headers are present.
- `GET /api/auth/me` returned HTTP 200 with `Cache-Control: no-store` and no active user.
- `POST /api/auth/register` returned HTTP 403 as intended.
- Desktop and mobile Playwright checks passed with no uncaught JavaScript errors or mobile horizontal overflow. Screenshots were captured from the live service.

Run evidence: https://github.com/Reisquin/Omnishelf/actions/runs/38826841911

## Free-tier limitations and cost guardrails

Render's Free web service sleeps after 15 minutes without inbound traffic and can take around a minute to wake. Its local filesystem is ephemeral; persistent library/account state must live in PostgreSQL. Render's Free PostgreSQL tier is not used because its databases expire after 30 days and do not include backups.

As documented in Neon's current Free plan documentation, the project allowance is **100 CU-hours per month, 0.5 GB of logical storage, and 5 GB of public network transfer per month**. Compute automatically scales to zero after five minutes of inactivity. Free-tier quotas are enforced: when compute or transfer limits are reached, the database compute is suspended until the next monthly window or an upgrade; writes that would exceed the storage cap fail. Neon documents no monetary overage billing on the Free plan. Review provider terms periodically because free-tier limits can change.

- Render Free services: https://render.com/docs/free
- Render Blueprint YAML: https://render.com/docs/blueprint-spec
- Render pricing/usage: https://render.com/pricing
- Neon plans: https://neon.com/docs/introduction/plans
- Neon Free-plan limits and quotas: https://neon.com/docs/introduction/plans#free-plan

## If the free service needs to be recreated

1. Use repository `Reisquin/Omnishelf`, branch `deploy/1.3.8-https-preview`, and Blueprint file `render.free.yaml`—not the default paid `render.yaml`.
2. Confirm the Blueprint contains exactly one web service set to **Free** and no Render-hosted database.
3. Create or select a Neon **Free** PostgreSQL project in Singapore. Use its pooled URI with SSL required.
4. Put the URI directly into Render's secret `DATABASE_URL` field. Never commit it, put it in screenshots, or paste it into chat.
5. Keep `COOKIE_SECURE=true` and `REGISTRATION_ENABLED=false`. If any provider asks to select a paid plan or authorize a charge, stop.

The active service was created directly in the confirmed Render workspace using the same free-only settings. The Render creation connector did not expose the native `healthCheckPath` setting; automated live smoke checks exercise `/healthz` after relevant pushes, while `render.free.yaml` declares it for any future Blueprint recreation.

## Acceptance tests still pending

Because public registration is intentionally disabled and no preview accounts have been created, full authenticated live account checks have not yet been performed. Pending items are login/session cookie flags on a successful live session, snapshot write/read across sign-in and redeploy, stale revision conflict (409), and isolation between two distinct test accounts. API-level tests for session flags, revision conflicts, and account isolation already pass against isolated SQLite in CI; PostgreSQL concurrent first-write locking has not yet been exercised against production dialect.

Do not enable public registration until account verification, password recovery, account deletion/export, shared abuse controls, backup/restore testing, and independent security and provider/licensing reviews are complete.
