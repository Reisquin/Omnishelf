# OmniShelf 1.3.8 deployment status

## Live free-first preview

- **Live URL:** https://omnishelf-1-3-8-free.onrender.com
- **Render service:** `omnishelf-1-3-8-free`, Free plan, Singapore.
- **Neon database:** Neon Free project `omnishelf-preview` in Singapore. The pooled connection string is stored in Render's `DATABASE_URL` secret and is not committed to the repository.
- **Source branch:** `deploy/1.3.8-https-preview`
- **Registration:** disabled (`REGISTRATION_ENABLED=false`).
- The existing 1.0.0 Render service and `main` branch remain untouched. The paid `render.yaml` remains an optional upgrade path; it was not used to create the live preview.
- No paid service/database was intentionally created.

## Verified live acceptance

The live smoke workflow passed: https://github.com/Reisquin/Omnishelf/actions/runs/38826841911

- `GET /healthz`: HTTP 200, database `ok`, app version `1.3.8`.
- Neon reports schema migration `001_initial_backend`; tables `users`, `sessions`, `state_snapshots`, and `alembic_version` exist.
- HTTPS HSTS and `X-Content-Type-Options: nosniff` confirmed.
- `GET /api/auth/me`: HTTP 200, `Cache-Control: no-store`, no signed-in user.
- `POST /api/auth/register`: HTTP 403, as intended.
- The app root returns HTTP 200. Live desktop/mobile browser checks passed with no uncaught JavaScript errors and no mobile horizontal overflow.
- Live desktop/mobile screenshots were captured in the workflow artifact `omnishelf-1.3.8-live-acceptance` (artifact is retained for 14 days).

## Remaining gaps

- Full authenticated live session-cookie verification cannot be completed until a controlled test session exists. The API-level cookie tests pass in CI.
- Live snapshot round-trip, sign-out/sign-in persistence, stale-revision (409), two-account isolation, and PostgreSQL first-write concurrency checks remain pending. Public registration stays disabled; do not expose a registration window just to test these.
- The Render API used to create the service did not expose its native health-check-path setting. The deployed smoke workflow explicitly checks `/healthz`; `render.free.yaml` declares `healthCheckPath: /healthz` for Blueprint-based recreation.
- No backup/restore drill or independent security review has been completed. Do not consider the site production-ready yet.

## Current free-tier constraints

- Render Free web services sleep after 15 minutes idle, use ephemeral local storage, and can take around a minute to wake.
- Neon's official Free plan currently lists 100 CU-hours, 0.5 GB storage, and 5 GB public network transfer per project per month. Compute scales to zero after five idle minutes. Free quotas suspend compute or prevent writes beyond limits rather than charging monetary overages.
- Official limits: https://neon.com/docs/introduction/plans
- Render free-service limits: https://render.com/docs/free

## Before public launch

Email verification, password recovery, account deletion/export, shared rate-limiting/abuse controls, backup and restore tests, independent security review, and provider/licensing review are still required. Keep public registration disabled until these are complete.
