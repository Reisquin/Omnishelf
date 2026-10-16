# OmniShelf 1.3.8 deployment status

## Live free-first preview

- **Live URL:** https://omnishelf-1-3-8-free.onrender.com
- **Render service:** `omnishelf-1-3-8-free`, Free plan, Singapore.
- **Neon database:** Neon Free project `omnishelf-preview` in Singapore. The pooled connection string is stored in Render's `DATABASE_URL` secret and is not committed to the repository.
- **Source branch:** `deploy/1.3.8-https-preview`
- **Registration:** disabled (`REGISTRATION_ENABLED=false`).
- The existing 1.0.0 Render service and `main` branch remain untouched. The paid `render.yaml` remains an optional upgrade path; it was not used to create the live preview.
- No paid service/database was intentionally created.

## Deployment correction — Render port binding — 2026-10-16

- Render deploy `dep-db8r1g6i0phs738nckq0` ultimately failed with “Port scan timeout reached, no open ports detected.” Build succeeded, but Render did not mark the cleanup commit live.
- The runtime log showed Uvicorn listening on port 10000 while the Dockerfile declared `EXPOSE 8000`. Corrected the Dockerfile to `EXPOSE 10000` and default Uvicorn to `PORT` or 10000. This aligns with Render's documented Docker port-binding recommendation: https://render.com/docs/multi-service-architecture.
- The CI deployment-config job now asserts the exposed port, all-interface binding, and `PORT` fallback match Render's expected configuration.
- **Resolved:** deploy `dep-db8rc5cs728c73aq5rp0` for commit `0ece07a50f900190e7e4db7bbc4a87e031ae62b8` reached Render status `live` at 2026-10-16 05:29:40 UTC. Runtime logs confirm Uvicorn listening on `0.0.0.0:10000`.
- **Post-deploy verification passed:** live smoke run [38855953928, attempt 2](https://github.com/Reisquin/Omnishelf/actions/runs/38855953928) succeeded after the new deployment was marked live. It checked PostgreSQL-backed health, HTTPS security headers, `Cache-Control: no-store`, anonymous cloud-state rejection (HTTP 401), closed registration (HTTP 403), the app shell, and desktop/mobile browser checks.
- Fresh post-deploy desktop/mobile PNGs are in the `omnishelf-1.3.8-live-acceptance` artifact (artifact ID `12026513359`, retained until 2026-10-30) and were extracted to the working session as `OmniShelf_1.3.8_Post_Deploy_Live_Desktop_Preview.png` and `OmniShelf_1.3.8_Post_Deploy_Live_Mobile_Preview.png`.

## Cleanup and rollout note — 2026-10-16

- Cleanup commit `ae896fd010d2194b4f13ebb68a9e4452f9ac4562` removes the temporary preview QA route from `backend/main.py`; the source was re-checked and no temporary route/token code remains.
- The temporary Render QA-token environment variable was set to an empty value before route removal and has not been re-enabled.
- Neon was checked after cleanup: `users`, `sessions`, and `state_snapshots` each contained zero rows; migration `001_initial_backend` remains applied. No test account or library state was left behind.
- Render deployment `dep-db8r1g6i0phs738nckq0` was ultimately marked `update_failed` because the port scan timed out. The exposed-port mismatch is documented and fixed in the subsequent `0ece07a` deployment above.
- The preceding smoke run `38853912858` did occur before that initial cleanup rollout and is not used as post-deploy evidence. The post-deploy smoke run listed above verifies the corrected deployment.
- Permanent safeguards are being added to CI to reject reintroduction of the temporary QA hook and to check that anonymous cloud-state reads return HTTP 401 with `Cache-Control: no-store`. This does not replace the still-pending authenticated hosted acceptance tests.

## Verified live acceptance

Latest live smoke workflow passed on 2026-10-16: https://github.com/Reisquin/Omnishelf/actions/runs/38851867077. PostgreSQL integration CI also passed against a separate disposable PostgreSQL 16 instance: https://github.com/Reisquin/Omnishelf/actions/runs/38851867171.

- `GET /healthz`: HTTP 200, database `ok`, app version `1.3.8`.
- Neon reports schema migration `001_initial_backend`; tables `users`, `sessions`, `state_snapshots`, and `alembic_version` exist.
- HTTPS HSTS and `X-Content-Type-Options: nosniff` confirmed.
- `GET /api/auth/me`: HTTP 200, `Cache-Control: no-store`, no signed-in user.
- `POST /api/auth/register`: HTTP 403, as intended.
- The app root returns HTTP 200. Live desktop/mobile browser checks passed with no uncaught JavaScript errors and no mobile horizontal overflow.
- Live desktop/mobile screenshots were captured in the workflow artifact `omnishelf-1.3.8-live-acceptance` (artifact is retained for 14 days).

## Remaining gaps

- Full authenticated live session-cookie verification cannot be completed until a controlled test session exists. API-level cookie tests pass in CI.
- Stale-revision (409) rejection, PostgreSQL concurrent first writes, sign-out/sign-in snapshot persistence, and per-account isolation now pass automated tests against a disposable PostgreSQL 16 CI database. Running those same authenticated scenarios against the hosted Render + Neon pair remains pending. Public registration stays disabled; do not expose a registration window just to test these.
- The Render API used to create the service did not expose its native health-check-path setting. The deployed smoke workflow explicitly checks `/healthz`; `render.free.yaml` declares `healthCheckPath: /healthz` for Blueprint-based recreation.
- No backup/restore drill or independent security review has been completed. Do not consider the site production-ready yet.

## Current free-tier constraints

- Render Free web services sleep after 15 minutes idle, use ephemeral local storage, and can take around a minute to wake.
- Neon's official Free plan currently lists 100 CU-hours, 0.5 GB storage, and 5 GB public network transfer per project per month. Compute scales to zero after five idle minutes. Free quotas suspend compute or prevent writes beyond limits rather than charging monetary overages.
- Official limits: https://neon.com/docs/introduction/plans
- Render free-service limits: https://render.com/docs/free

## Before public launch

Email verification, password recovery, account deletion/export, shared rate-limiting/abuse controls, backup and restore tests, independent security review, and provider/licensing review are still required. Keep public registration disabled until these are complete.


## Authenticated flow coverage — production-mode PostgreSQL test

Date: 2026-10-16

- Extended `backend/tests/test_postgres_integration.py` with a production-mode HTTP-route test against the disposable PostgreSQL CI service. It seeds test accounts only in the isolated CI database, then closes registration while verifying that an existing account can still log in over HTTPS.
- The test asserts Secure/HttpOnly/SameSite=Lax session-cookie attributes, HSTS and `Cache-Control: no-store`, cloud-state save/read, stale revision HTTP 409 without overwrite, session revocation on logout, restore after a fresh sign-in, anonymous HTTP 401, and account isolation.
- This closes a gap in the PostgreSQL regression suite, but it is still **not** a live authenticated Render + Neon test. Production hosted credentials remain unavailable for a safe controlled run; registration stays closed.


- **Latest expanded CI result:** [run 38856765191](https://github.com/Reisquin/Omnishelf/actions/runs/38856765191) passed all five jobs, including the new HTTPS + registration-closed PostgreSQL integration scenario. It only used a disposable GitHub Actions PostgreSQL 16 database.
- **Latest live smoke + screenshot result:** [run 38856765111](https://github.com/Reisquin/Omnishelf/actions/runs/38856765111) passed after the port fix. Fresh desktop/mobile snapshots are in artifact `omnishelf-1.3.8-live-acceptance` (ID `12027606745`, retained through 2026-10-30) and extracted as `OmniShelf_1.3.8_Auth_Check_Live_Desktop_Preview.png` and `OmniShelf_1.3.8_Auth_Check_Live_Mobile_Preview.png`.
- A read-only Neon check confirmed `users=0`, `sessions=0`, `state_snapshots=0`; the migration marker remains present. No hosted test accounts or saved state were created.
