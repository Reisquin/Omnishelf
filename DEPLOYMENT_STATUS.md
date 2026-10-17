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

- Post-deployment live smoke and authenticated staging acceptance both passed in run 38871388659 after the new deployments completed. The isolated staging test verified current hosted auth/session behavior and the account flows.
- Hosted authenticated session, concurrent-save, stale-revision, logout/re-login persistence, two-account isolation, data export, and password-confirmed deletion tests now pass against the real staging Render + Neon pair. Public registration stays disabled; do not expose a registration window just to test these.
- The Render API used to create the service did not expose its native health-check-path setting. The deployed smoke workflow explicitly checks `/healthz`; `render.free.yaml` declares `healthCheckPath: /healthz` for Blueprint-based recreation.
- Manual native-snapshot/restore and data-bearing PostgreSQL dump/restore drills passed on 2026-10-16. Automated snapshot scheduling is not enabled for this Neon project, so recurring backup policy remains open; independent security review is also pending. Do not consider the site production-ready yet.

## Current free-tier constraints

- Render Free web services sleep after 15 minutes idle, use ephemeral local storage, and can take around a minute to wake.
- Neon's official Free plan currently lists 100 CU-hours, 0.5 GB storage, and 5 GB public network transfer per project per month. Compute scales to zero after five idle minutes. Free quotas suspend compute or prevent writes beyond limits rather than charging monetary overages.
- Official limits: https://neon.com/docs/introduction/plans
- Render free-service limits: https://render.com/docs/free

## Before public launch

Email verification, password recovery, additional abuse controls beyond shared IP-based login/registration throttles, an enabled production backup schedule/retention policy, independent security review, and provider/licensing review remain required. Data export and password-confirmed account deletion are implemented and tested. The backup/restore drill passed, but automated snapshots are not enabled for this Neon project. Keep public registration disabled until the remaining controls are complete.


## Authenticated flow coverage — production-mode PostgreSQL test

Date: 2026-10-16

- Extended `backend/tests/test_postgres_integration.py` with a production-mode HTTP-route test against the disposable PostgreSQL CI service. It seeds test accounts only in the isolated CI database, then closes registration while verifying that an existing account can still log in over HTTPS.
- The test asserts Secure/HttpOnly/SameSite=Lax session-cookie attributes, HSTS and `Cache-Control: no-store`, cloud-state save/read, stale revision HTTP 409 without overwrite, session revocation on logout, restore after a fresh sign-in, anonymous HTTP 401, and account isolation.
- This closes a gap in the PostgreSQL regression suite, but it is still **not** a live authenticated Render + Neon test. Production hosted credentials remain unavailable for a safe controlled run; registration stays closed.


- **Latest expanded CI result:** [run 38856765191](https://github.com/Reisquin/Omnishelf/actions/runs/38856765191) passed all five jobs, including the new HTTPS + registration-closed PostgreSQL integration scenario. It only used a disposable GitHub Actions PostgreSQL 16 database.
- **Latest live smoke + screenshot result:** [run 38856765111](https://github.com/Reisquin/Omnishelf/actions/runs/38856765111) passed after the port fix. Fresh desktop/mobile snapshots are in artifact `omnishelf-1.3.8-live-acceptance` (ID `12027606745`, retained through 2026-10-30) and extracted as `OmniShelf_1.3.8_Auth_Check_Live_Desktop_Preview.png` and `OmniShelf_1.3.8_Auth_Check_Live_Mobile_Preview.png`.
- A read-only Neon check confirmed `users=0`, `sessions=0`, `state_snapshots=0`; the migration marker remains present. No hosted test accounts or saved state were created.

## Browser-level cloud-sync UI acceptance — 2026-10-16

- Added scripts/test_cloud_sync_ui.py and wired it into the frontend-layout-preview CI job.
- The Playwright run exercises the account modal, sign-in, first cloud upload, stale-revision conflict messaging, restore from a newer cloud snapshot, and preservation of browser-local data after sign-out. The UI calls are served by a local deterministic mock API; this test does not connect to Render or Neon and does not create hosted accounts or modify hosted libraries.
- Passed: CI run [38860148427](https://github.com/Reisquin/Omnishelf/actions/runs/38860148427), all five jobs successful, including the mocked cloud-sync browser flow and PostgreSQL integration tests.
- The workflow generated desktop, mobile, and connected-account-panel screenshots in artifact omnishelf-1.3.8-layout-previews (artifact ID 12028942100, available until 2026-10-30). The connected-account screenshot was extracted as omnishelf-1.3.8-cloud-sync-connected.png.
- This improves frontend regression coverage but does not close the pending authenticated live Render + Neon acceptance gap. Do not infer live cloud persistence from a mocked UI test; public registration remains disabled.

## Isolated authenticated staging lane — 2026-10-16

- Created a dedicated Neon branch named auth-staging-2026-10-16 (br-tiny-moon-ao9v8tny) from the preview database. It is separate from the primary branch (br-mute-lake-aonh60ev).
- Created a separate Render Free web service, omnishelf-1-3-8-auth-staging (srv-db8s513bc2fs73c0a9v0), in Singapore at https://omnishelf-1-3-8-auth-staging.onrender.com. It points to the staging database branch; the connection URI is held only in Render environment configuration and is not committed to the repository.
- The staging service has REGISTRATION_ENABLED=false, COOKIE_SECURE=true, and same-origin HTTPS configuration. No public sign-up window was opened.
- The staging branch was checked read-only after deployment: users=0, sessions=0, state_snapshots=0; migration 001_initial_backend is present.
- Passed staging smoke and screenshot workflow: [run 38860955820](https://github.com/Reisquin/Omnishelf/actions/runs/38860955820). It checks PostgreSQL-backed /healthz, HTTPS HSTS and nosniff, anonymous auth identity, anonymous state denial (401/no-store), closed registration (403), root page, JavaScript errors, and mobile overflow. The same workflow also passed the pre-existing live preview smoke checks.
- Staging screenshots are in artifact omnishelf-1.3.8-auth-staging-previews (artifact ID 12028079809, available until 2026-10-30), extracted as omnishelf-1.3.8-auth-staging-desktop.png and omnishelf-1.3.8-auth-staging-mobile.png.
- Closed later on 2026-10-16: hosted authentication, cloud save/read, stale-revision handling, relogin persistence and two-account isolation passed in run 38862355701; data export and account deletion passed in run 38866747552. Both runs used ephemeral accounts and cleaned up their own test records. Registration remains disabled.

## Hosted authenticated acceptance — passed 2026-10-16

- Implemented a self-cleaning hosted acceptance runner at scripts/live_staging_auth_acceptance.py. It requests a short-lived GitHub Actions OIDC token (no stored runner password or database connection string), then calls a narrow seeding/cleanup hook mounted only on the dedicated staging service when OMNISHELF_STAGING_ACCEPTANCE_ENABLED=true.
- The staging hook verifies GitHub's signed OIDC token, issuer, audience, repository, branch ref, workflow path, push event, run ID, and run attempt. It fails closed unless the service origin is the expected staging URL, HTTPS-only cookies are enabled, and ordinary registration is disabled. The regular free blueprint does not set the staging enable flag, and CI checks that the route is absent on the ordinary live preview.
- Authenticated live test passed: [workflow run 38862355701](https://github.com/Reisquin/Omnishelf/actions/runs/38862355701). Against the real staging Render + Neon service it verified:
  - Two runtime-generated test accounts were created through the OIDC-gated hook; no credentials were logged.
  - Existing-account login worked over HTTPS with Secure, HttpOnly, SameSite=Lax cookies and no-store/HSTS headers while normal public registration remained HTTP 403.
  - Two concurrent first snapshot saves produced exactly one success and one HTTP 409 conflict.
  - A stale revision was rejected without overwriting the committed snapshot.
  - Logout revoked the session; signing back in restored the saved snapshot from PostgreSQL.
  - A second account started with an empty snapshot and remained isolated from the first account's saved library.
  - Test cleanup removed both temporary accounts and all associated snapshots/sessions.
- Post-test read-only verification: both the staging branch and primary preview branch report users=0, sessions=0, and state_snapshots=0, with migration 001_initial_backend applied.
- CI passed: [run 38862355750](https://github.com/Reisquin/Omnishelf/actions/runs/38862355750); all five jobs passed. Both staging and pre-existing preview smoke jobs succeeded in [run 38862355701](https://github.com/Reisquin/Omnishelf/actions/runs/38862355701).
- Latest screenshots are in omnishelf-1.3.8-auth-staging-previews (artifact ID 12029526545) and omnishelf-1.3.8-live-acceptance (artifact ID 12029118953), available through 2026-10-30.
- Remaining public-launch work is unchanged: email verification/recovery/deletion/export, shared abuse/rate limits, backup and restore drill, independent security review, and provider/licensing review. The acceptance harness is not a public feature and regular registration remains disabled.

## Backup and restore drill — 2026-10-16

- **Data-bearing logical backup + restore passed in CI:** [run 38864850286](https://github.com/Reisquin/Omnishelf/actions/runs/38864850286), all five jobs green. The new scripts/backup_restore_drill.py seeds one non-login fixture in the disposable PostgreSQL 16 CI service, makes a custom-format pg_dump archive, restores it into a fresh database with pg_restore, and compares the migration version, four application/migration tables, snapshot foreign key, account row, revision 42, and exact library-canary payload. The 7,233-byte archive was kept only in the ephemeral runner and never uploaded. The restore database is dropped by the script; the test source is discarded with the CI service.
- **Native Neon snapshot/restore completed:** manual snapshot snap-nameless-thunder-ao24daoi (omnishelf-backup-restore-drill-2026-10-16) was created from the original primary branch br-mute-lake-aonh60ev. A separate recovered branch br-holy-meadow-aoztug2u was restored from it. Read-only queries on the original and recovered branches show users=0, sessions=0, state_snapshots=0 and migration 001_initial_backend; this native snapshot validates recovery of the empty baseline schema/migration marker, while the CI dump/restore test validates recovery of non-empty account/library rows.
- The original primary branch is again named main and is both primary=true and default=true. The recovered branch remains separate and non-default. Staging and primary branch row counts remain empty.
- **Recurring backup schedule is not configured:** an attempt to set a daily schedule on the primary branch was rejected because “backup schedule creation is not enabled for this project.” The manual snapshot expires at 2026-10-30T00:00:00Z; it is a drill/recovery point, not a long-term recurring policy.
- One isolated drill-source branch (br-old-violet-aoe919fi, backup-restore-drill-source-2026-10-16) retains exactly one synthetic, non-login canary account and its snapshot as test evidence. It is not the primary or staging branch and no Render service uses it. It was not deleted because branch deletion/data deletion is destructive; remove it only after explicit approval.
- Latest live-preview smoke passed in [run 38864850271](https://github.com/Reisquin/Omnishelf/actions/runs/38864850271). Desktop/mobile screenshots are in artifact omnishelf-1.3.8-live-acceptance, ID 12030607732, available until 2026-10-30.

## Account data export and self-service deletion — 2026-10-16

- Added authenticated API route GET /api/me/export, returning a downloadable JSON account export with account metadata and the cloud snapshot. The document excludes password hashes, session token hashes, and session records; the response is an attachment with Cache-Control: no-store.
- Added DELETE /api/me/account. It requires the current password and an allowed origin, rejects an incorrect password, deletes the caller's cloud snapshot and all server-side sessions, deletes the account, and expires the current browser's session cookie. It does not clear the separate local browser library.
- Added account-panel UI controls: “Download my account data” and “Delete account”. The deletion flow warns that removal is permanent and asks for the current password.
- All five CI jobs passed: [run 38866747602](https://github.com/Reisquin/Omnishelf/actions/runs/38866747602), including isolated API tests, PostgreSQL integration tests, the new account export/delete cases, the mocked browser journey, and layout screenshots.
- Hosted staging acceptance passed: [run 38866747552](https://github.com/Reisquin/Omnishelf/actions/runs/38866747552). It verified exported JSON contains the account's library and no password/session secrets, incorrect-password deletion is refused, valid deletion removes cloud state and revokes multiple sessions, and deleting the second account does not affect the first account's library. Two random accounts were created; the secondary was deleted by the test and the cleanup hook removed the remaining temporary account.
- Both hosted deployments now run commit bb61134d992ec895c1f98c441f4b8286dbde7ea7: the staging deployment is dep-db8t0davcj2c73b45t10 and the separate 1.3.8 preview deployment is dep-db8t0ejl550s73f3i9d0. The original 1.0.0 service and main source branch remain untouched.
- Post-test read-only checks confirmed both primary and staging branches have zero users, sessions, and snapshots. Public registration remains disabled.
- Fresh previews are in workflow artifacts omnishelf-1.3.8-auth-staging-previews (ID 12031282360), omnishelf-1.3.8-live-acceptance (ID 12030914679), and omnishelf-1.3.8-layout-previews (ID 12031442078), retained through 2026-10-30.

## Shared authentication rate limiting — 2026-10-16

- Replaced the process-local login/registration counters with the versioned auth_rate_limits PostgreSQL table. Atomic INSERT .. ON CONFLICT DO UPDATE enforces fixed windows across workers/instances; SQLite uses the corresponding atomic upsert for isolated tests.
- Default limits remain 5 registrations per client IP per hour and 10 login attempts per client IP per 15 minutes. Blocked attempts return HTTP 429 with Retry-After; counters cap at limit+1, and expired keys are opportunistically pruned.
- Client addresses are HMACed before storage (no raw IP address is stored). RATE_LIMIT_HASH_KEY can explicitly set the stable key; absent that, the shared DATABASE_URL is used so all instances connected to that database compute the same hash. When RENDER=true, the app reads the first platform-provided X-Forwarded-For entry; local/self-hosted requests do not trust caller-supplied forwarding headers.
- Failure to reach the shared rate-limit table fails closed with HTTP 503 rather than silently disabling protection.
- Added Alembic migration 002_shared_auth_rate_limits; the staging deployment reports that revision and the table exists.
- CI run 38870722468 passed all five jobs, including cross-client window expiry and a concurrent PostgreSQL test where 8 simultaneous login attempts produced exactly 3 allowed failures and 5 HTTP 429 responses.
- Post-deployment hosted smoke/acceptance run 38871388659 passed after both new deployments were live; the authenticated staging route test completed at 08:06 UTC. Treat this run, rather than earlier overlapping runs, as the current live evidence.
- Source commit 2eecb50ef2868f2e9c17dfc4f294953a70bf4ccf is live in the isolated staging and preview services. The main release service remains untouched. Public registration stays disabled.

## Final rate-limit validation after deployment — 2026-10-16

- The source code commit 2eecb50ef2868f2e9c17dfc4f294953a70bf4ccf is live on both isolated Render 1.3.8 services. Startup logs for each service record the Alembic upgrade from 001_initial_backend to 002_shared_auth_rate_limits.
- Post-deployment live acceptance passed in [run 38871388659](https://github.com/Reisquin/Omnishelf/actions/runs/38871388659); the authenticated staging test completed after the staging deployment had become live. Registration remains closed. The staging Neon branch reports migration 002, zero users, zero sessions, and zero snapshots after test cleanup.
- The latest five-job code/test CI passed in [run 38871388595](https://github.com/Reisquin/Omnishelf/actions/runs/38871388595). The rate-limit regression now also varies later X-Forwarded-For hops while holding the first client IP constant, confirming those requests share a bucket.
- Fresh screenshot artifacts: auth staging previews ID 12033323664, live preview screenshots ID 12033277508, and layout previews ID 12032499043 (available through 2026-10-30). The combined local screenshot package is linked in the task summary.
- Known connection-mapping discrepancy: querying the only currently listed Neon project's primary branch still returns 001_initial_backend and no auth_rate_limits table, although Render's preview startup log shows that revision 002 was applied to its configured PostgreSQL. The 1.3.8 preview's actual DATABASE_URL target is not exposed by the available read-only Render service metadata; verify that mapping before assuming Neon main is that service's database. Do not alter database URLs or repoint the service without confirming the intended target.



## Feature build 1.3.9 — email verification and password recovery
Date: 2026-10-18

- Created isolated branch `feature/1.3.9-email-verification-password-reset` from the accepted 1.3.8 HTTPS preview. This is a code branch only: it has not been merged or deployed, and the 1.3.8 live service remains unchanged.
- Added migration `003_email_verification_and_reset`: records an email-verification timestamp, marks accounts created before this feature as verified so existing logins survive, and adds a token table with single-purpose hashes, expiry, and cascading account deletion.
- Added account verification, resend-verification, password-reset request, and password-reset confirmation endpoints. Verification/reset tokens are random, stored as SHA-256 hashes, expire (24h/30m defaults), and are serialized with a row lock when consumed. Password recovery changes the Argon2 hash and revokes all server sessions.
- Added rate-limit buckets for verification and reset requests/actions; generic request responses avoid revealing whether an email belongs to an account. Hosted mail requires STARTTLS, a configured sender, and the trusted HTTPS `PUBLIC_APP_ORIGIN`. If mail is not configured, signup/recovery fails closed; hosted public registration remains disabled.
- Added sign-in UI links for forgotten passwords and resending verification email, a reset-password form, email-link handling, API tests using a mocked mail sender, PostgreSQL integration coverage, and Playwright UI coverage. The build version and desktop/mobile screenshot artifact labels are 1.3.9.
- Validation status at note creation: source and CI configuration committed on the feature branch, but CI has not yet been reported green. Do not call this release-ready until the pull-request checks and screenshot artifact succeed.
- Remaining before any deployment: configure and test an SMTP sender in secret settings; verify the preview service's real Neon target instead of assuming it is the currently listed primary branch; reconcile migration target; retain public registration disabled; then complete backup-retention, independent security and provider/licensing reviews.
