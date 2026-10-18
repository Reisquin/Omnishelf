# OmniShelf — Project Progress Log

This file is the durable running record of OmniShelf decisions, milestones, current status, blockers, and next actions. Update it whenever a meaningful build or project decision is made. Keep prior milestones; append or revise current-status sections rather than discarding history.

Last verified: 2026-10-16
Current tracked build: **1.3.8**
Active working branch: `deploy/1.3.8-https-preview`

## Product direction and enduring requirements

- OmniShelf is a universal storytelling/media catalogue and personal tracking platform: “AniList, but designed from day one for all storytelling rather than only anime and manga.”
- Establish AniList feature parity first, then extend the experience across supported storytelling mediums.
- Retain the full project history in subsequent builds; don't treat each update as a fresh project.
- Provide a screenshot or visual preview for every build/update.
- User does not want to be expected to handle web-development implementation personally; keep instructions understandable and handle technical work wherever connected tools allow.
- Key profile preferences: favourites are image-only grids with tooltip labels on hover; show Top 25 favourites on profile overview and Top 100 in the favourites section; profile activity belongs to that profile owner, while broader activity belongs on Home; reviews visibly identify the reviewed work and cover.
- Favourites ordering: Works first, then Characters, medium-specific favourites, Arcs/Routes/Parts, Dynamics, and People. Category names should be plain (e.g. “Works”, “Anime”), without explanatory brackets.

## Catalogue scope

Supported mediums:
Anime; Manga; Manhwa; Manhua; Novel; Light Novel; Web Novel; Visual Novel; Game/Video Game; Movie; TV; Comics; Narrative Poetry; Poetry; Play; Short Story; Short Story Collection; Novella.

Taxonomy choices recorded:
- Epic/oral tradition is included under Novels.
- Memoir/Autobiography is handled under Non-fiction.
- Documentary is included within Movies.
- Screenplays, Audiobooks, Podcasts, Operating, Musical Theatre, Librettos, Interactive Fiction, Gamebooks, and standalone Radio Drama are not separate supported mediums.

## Milestone history

- **v0.21** — Provider Hub foundation.
- **v0.54** — AniList implementation/technical acceptance preparation.
- **v0.58** — IGDB established as a first-class game provider.
- **v0.59** — Cross-provider identity and reconciliation.
- **v0.60** — Unified enrichment engine.
- **v0.62** — Unified provider search.
- **v0.63** — Data-governance layer.
- **v0.64** — Explore landing surface.
- **v0.65** — Asian dramas experience.
- **v0.66** — Medium Experience Framework registry.
- **v0.67** — Canonical catalogue product experience.
- **v0.68** — Deep-linkable work pages.
- **v0.69** — Personal Library Experience: personal status, progress and unit/total, 1–100 personal score, favourites, notes, started/completed dates, and medium-aware progress inference.
- **v0.73** — Read-only Personal Statistics 2.0.
- **v0.76** — Provider-neutral local Social / Community 2.0 layer.
- **v0.77** — Universal Import / Export and migration.
- **v0.78** — Full medium-by-medium personal experiences.
- **v0.79** — UI/UX and accessibility finalisation.
- **v0.80** — Production hardening.
- **v0.81** — Final release candidate and completion audit.
- **1.0.0** — Production-release package prepared from the v0.81 RC. This was a version-freeze/package step, not a new feature milestone; the source repository's `main` branch retains the 1.0.0 download archive.
- **1.2.3** — Source comments identify Top 25 profile overview favourites, Top 100 favourites page, and profile parity additions (search filters, score preferences, mass list editing).
- **1.3.3** — Source comments identify stable work deep links and editable relationship metadata.
- **1.3.8** — Persistence and backend foundation; see detailed checkpoint below.

## Current checkpoint — 1.3.8

### Verified source/build state
- The isolated branch `deploy/1.3.8-https-preview` contains the single-page frontend in root `index.html`, a `static-preview/index.html`, FastAPI backend code under `backend/`, Alembic migration structure, Dockerfile, Render blueprint, deployment status, and deployment checklist.
- Frontend title/version metadata and FastAPI app metadata identify version 1.3.8.
- Backend source includes account/session and revisioned snapshot foundations, password hashing, rate-limit code, and `/healthz`.
- The frontend-only HTTPS preview is documented as: https://omnishelf-1-3-8-preview.onrender.com
- The project has a documented preview URL, but live availability has not been independently confirmed in the latest check.
- Original source baseline when the 1.3.8 checkpoint was first inspected: `b3faa2fc957b0251e488fbb90bd267af1b9060fe` (2026-10-15), “Label hosted frontend as preview while backend awaits billing setup.”
- Latest known `main` branch commit in the connected repository is `af5698fe1ba902d65e45028615060f9291332f3f` (2026-10-07); `main` contains the 1.0.0 archive. The 1.3.8 branch is kept separate.

### Known limitations/blockers
- The original static preview URL remains frontend-only. A separate free-first full app/API service is now live at https://omnishelf-1-3-8-free.onrender.com, backed by Neon Free PostgreSQL.
- Historical blocker: paid Render PostgreSQL provision returned HTTP 402. Resolved for the controlled preview by using Neon Free PostgreSQL instead. No paid database or paid backend service was intentionally created; a Render Free web service now exists.
- Deployment acceptance checks remain open: database health, migrations, secure session-cookie checks, registration disabled, snapshot persistence after redeploy/sign-out/sign-in, stale-revision handling, isolation between test accounts, frontend console checks on desktop/mobile, and screenshots from the exact deployed commit.
- Public launch still requires email verification, password recovery, account deletion/export, shared rate limiting and abuse prevention, backups/restore testing, security review, and provider/licensing review.
- Keep public registration disabled until these issues are addressed. Do not claim cloud persistence, account isolation, or production readiness without passing the respective tests.

## Next actions

1. Finish authenticated live integration tests with controlled temporary test accounts without enabling public registration.
2. Verify stale-revision conflict and PostgreSQL concurrent first-write handling against Neon.
3. Configure native Render healthCheckPath through the dashboard/Blueprint if supported; the smoke workflow already exercises `/healthz`.
4. Complete email verification/recovery/deletion/export, shared abuse controls, database backup/restore drill, and independent security/licensing reviews before considering public registration.

## Completed work step — backend verification and favourites layout correction

Date: 2026-10-16

- Added `backend/tests/test_api.py` with 9 isolated SQLite-backed API tests covering health/version and safety headers, registration-disabled behaviour, identity normalization, session-cookie attributes, duplicate rejection, origin guards, cloud-state round trips, stale-revision protection, per-account snapshot isolation, invalid state payloads, and logout/session revocation.
- Added `.github/workflows/omnishelf-1-3-8-checks.yml` with CI jobs for API tests, fresh SQLite Alembic migrations, and Playwright desktop/mobile screenshot capture.
- Updated both `index.html` and `static-preview/index.html` so favourite groups render in the requested order: **Works → Characters → Anime → Manga → Novels → Short Stories → Arcs → Writers → Dynamics → People**.
- Added a Playwright assertion to the layout-preview job so the expected favourites order is checked against the rendered page, not merely against the source array.
- **Verified CI run:** https://github.com/Reisquin/Omnishelf/actions/runs/38820246491 — all three jobs completed successfully: `backend-tests`, `migration-check`, and `frontend-layout-preview`. The order assertion passed. The follow-up workflow-only commit `fb1d3716ad8f9c9136681bdc5e5317327fa9dbb1`, which excludes progress-log-only changes from triggering a full CI run, also passed all three jobs: https://github.com/Reisquin/Omnishelf/actions/runs/38820388548.
- CI uploaded real Playwright screenshot artifacts as `omnishelf-1.3.8-layout-previews`. The desktop and mobile snapshots shown alongside this step were captured from the HTML in the repository, not reconstructed mockups. The live preview URL remains https://omnishelf-1-3-8-preview.onrender.com.
- No Render resources were created and no paid deployment was attempted. The prior deployment record still identifies billing as the blocker for provisioning the isolated PostgreSQL-backed service.
- Current source/layout correction commits: root `index.html` at `0248b50f892c61f1d2596a503a8ae83e86aa158d`; static preview at `38d1e629eef4940ea5a4ba5fbadc400d61734761`; layout-order assertion at `510ba90fcfbe72302086a0783241d2b500fca1e9`.
- Next: finish verifying the workflow-only trigger adjustment, then move to backend deployment readiness after billing and resource-authorization prerequisites are resolved.

## Completed work step — backend deployment-readiness audit

Date: 2026-10-16

- Expanded `backend/tests/test_api.py` with three more tests: secure cookie flags and HSTS under HTTPS, oversized request rejection before route parsing, and serving the real 1.3.8 frontend alongside the API root. Total isolated API test functions: 12.
- Hardened `backend/main.py` snapshot saving: `PUT /api/me/state` now locks the authenticated user's stable database row before locking/checking the snapshot. This serializes concurrent writes per user on PostgreSQL even during the first save, when a snapshot row does not yet exist. SQLite does not implement PostgreSQL's row-lock semantics, so production-dialect concurrency must still be verified after deployment.
- Strengthened `.github/workflows/omnishelf-1-3-8-checks.yml`: CI now fails on uncaught Playwright JavaScript errors and mobile horizontal page overflow, and checks the approved profile favourites order before saving desktop/mobile screenshots.
- **Verified CI run after the backend code changes:** https://github.com/Reisquin/Omnishelf/actions/runs/38823563199 — all jobs passed on commit `1e163429545c4ab175364d6d7817469e2ac34d11`: `backend-tests`, `migration-check`, and `frontend-layout-preview`.
- **Latest full CI run:** https://github.com/Reisquin/Omnishelf/actions/runs/38823691361 — all three jobs passed again after the deployment checklist update. Preview artifact from this run: `omnishelf-1.3.8-layout-previews` (desktop and mobile PNGs, retained by GitHub Actions until 2026-10-29).
- Updated `DEPLOYMENT_CHECKLIST.md` to mark successful CI checks and explicitly leave PostgreSQL-specific concurrency and live-deployment acceptance checks open.
- **Deployment remains gated:** no Render database/service was created. The existing record quotes roughly $13/month before overages for the separate service and managed database, and records a billing prerequisite. The connected Render workspace still must be confirmed before any cloud-resource action. Public account registration stays disabled.
- Next: obtain explicit confirmation of the Render workspace and budget for the separate resources; then deploy only the isolated backend, run its real PostgreSQL acceptance checks, and capture a preview from that deployment. Never change the existing 1.0.0 service or main branch as part of this step.

## Working rule for future turns

After each meaningful project step:
- update this log with the version, changed files, decisions, test results, blockers, and next action;
- preserve earlier milestones and user requirements;
- distinguish source code, local test results, preview deployment, verified cloud persistence, and production launch as separate states;
- include a screenshot/visual preview for every build/update where feasible;
- never describe an unverified build, deploy, integration, or test as completed.


## Completed work step — free-first deployment preparation

Date: 2026-10-16

- Added `render.free.yaml` with a separate Docker web service named `omnishelf-1-3-8-free`, the Render `free` plan, the existing isolated branch, `/healthz` health check, HTTPS Secure cookies, disabled registration, and a dashboard-only `DATABASE_URL` secret. It intentionally does not create a Render Postgres database.
- Preserved the existing paid `render.yaml` only as an optional future upgrade path. The existing `main` branch and 1.0.0 service remain untouched.
- Added `FREE_DEPLOYMENT_GUIDE.md` documenting Neon Free PostgreSQL, the requirement to keep its pooled connection URI secret, Render Free sleep/storage/usage limitations, setup sequence, safety constraints, and live acceptance tests.
- Updated `DEPLOYMENT_STATUS.md` and `DEPLOYMENT_CHECKLIST.md` to reflect that the free-first configuration is prepared but not yet deployed.
- Added a CI job that parses the free blueprint and fails closed unless it defines exactly one Free web service, no Render-managed database, secret-only `DATABASE_URL`, `COOKIE_SECURE=true`, and `REGISTRATION_ENABLED=false`.
- Current external-provider facts checked against official documentation on 2026-10-16: Render documents that Free web services sleep after 15 idle minutes, local files are ephemeral, and its Free Postgres instances expire after 30 days without backups; Neon announced on 2026-10-02 that its Free plan includes 1 GB Postgres storage per project. These provider limits can change.
- No Render service or database has been created by this preparation step and no paid resource has been created. Actual deployment still requires explicit workspace selection and a Neon Free project/connection URI. Never commit a connection URI or send it through chat.
- Next actions: validate CI, confirm the intended Render workspace, connect Neon, create only the Free web service, and then run the live backend acceptance checklist. Keep public registration disabled.


## Validation result — free-first build checks

Date: 2026-10-16

- GitHub Actions run **38825891605** succeeded across all four jobs: backend API tests, fresh-database migration check, free deployment blueprint safety validation, and desktop/mobile layout preview.
- The free blueprint guard passed: one free web service only; no Render-managed database; Neon `DATABASE_URL` kept dashboard-secret-only; registration disabled; Secure cookies retained.
- The latest Playwright artifact is [`omnishelf-1.3.8-layout-previews`](https://github.com/Reisquin/Omnishelf/actions/runs/38825891605). Preview files captured from that run are available in the current ChatGPT working session as `OmniShelf_1.3.8_FreeFirst_Desktop_Crop.png` and `OmniShelf_1.3.8_FreeFirst_Mobile_Crop.png`.
- These are layout-validation screenshots, not deployed-backend screenshots. Cloud account/sync acceptance remains pending until a Neon Free database is connected and the separate Render Free service is created.


## Deployment handoff — Render workspace confirmed

Date: 2026-10-16

- User explicitly confirmed using Render's `My Workspace` for the free-first deployment.
- Read-only resource inventory completed in workspace `tea-db364u7lk1mc739i8udg`: found the existing 1.3.8 static preview and the original 1.0.0 web service; no Render Postgres instances exist. No existing services were modified.
- Neon is not connected to the current session yet. A Neon connection option was surfaced again so the user can authorize it; until connection and a Free Neon project/pooled URI are available, do not create a backend service that would silently use ephemeral SQLite for supposedly cloud-persistent account data.
- Next action after Neon is connected: confirm/create a Neon Free Postgres project, keep the connection URI out of chat and Git, deploy only the Render Free service from `render.free.yaml` into the confirmed workspace, and execute live acceptance checks. If any step asks to select a paid plan or authorize a charge, stop.
- No paid resources created. Registration remains disabled. Existing `main` and 1.0.0 deployment remain untouched.


## Completed work step — Free-first backend deployed and live-smoke tested

Date: 2026-10-16

- User explicitly approved using Render `My Workspace`, connecting Neon, and choosing only free-tier resources.
- Created Neon Free project `omnishelf-preview` in Singapore (`aws-ap-southeast-1`), PostgreSQL 17. Endpoint autoscaling was constrained to 0.25 CU minimum/maximum, and transaction-mode pooling was enabled. The endpoint defaults to provider scale-to-zero behavior; the account did not permit modifying the suspend interval, so no suspend override was applied.
- The Neon pooled PostgreSQL URI was sent directly into the Render service's `DATABASE_URL` secret. It was not written to GitHub or project files, and it must not be disclosed in chat or screenshots.
- Created Render web service `omnishelf-1-3-8-free` with plan `free`, Singapore region, Dockerfile, branch `deploy/1.3.8-https-preview`, `COOKIE_SECURE=true`, `REGISTRATION_ENABLED=false`, 30-day session TTL and 20 MB state limit. Service URL: https://omnishelf-1-3-8-free.onrender.com
- Render deploy `dep-db8mgotg1s2s73832n3g` reached `live`; build succeeded, app started, and Alembic ran migration `001_initial_backend` using PostgreSQL. Neon verified `alembic_version=001_initial_backend` and the `users`, `sessions`, `state_snapshots` and `alembic_version` tables.
- Added `.github/workflows/omnishelf-1-3-8-live-smoke.yml` to check the live service on relevant pushes, retrying while the Render Free instance wakes. Live smoke run **38826841911** succeeded: `/healthz` 200, DB `ok`, version 1.3.8, HSTS present, nosniff present, `/api/auth/me` 200 with `Cache-Control: no-store`, registration 403, root page 200, no uncaught desktop/mobile JavaScript errors, and no mobile horizontal overflow.
- Captured full-page screenshots from the actual deployed service (not only local static HTML); artifact `omnishelf-1.3.8-live-acceptance` is attached to the successful run for 14 days. Screenshots were also extracted to the current working session as `OmniShelf_1.3.8_Live_Desktop_Preview.png` and `OmniShelf_1.3.8_Live_Mobile_Preview.png`.
- Corrected the Free-tier guide based on Neon’s current official plan documentation checked on 2026-10-16: 100 CU-hours, 0.5 GB logical storage and 5 GB public network transfer per project per month, with compute scale-to-zero after five minutes; free quota exhaustion suspends compute or rejects over-cap writes rather than causing monetary overage billing. Source: https://neon.com/docs/introduction/plans
- The Render create-service connector did not expose the native `healthCheckPath` setting; the live smoke workflow explicitly checks `/healthz` and the checked-in `render.free.yaml` declares the path for future Blueprint recreation.
- No paid resource was intentionally created. The existing 1.0.0 service and `main` branch remain untouched. Public registration remains disabled.
- Still pending against the hosted Render + Neon preview: successful authenticated session-cookie check, cloud snapshot round-trip across sign-out/sign-in, stale-revision conflict, and two-account isolation. These now have automated coverage against a disposable PostgreSQL 16 CI database, but the hosted authenticated path remains untested until a controlled test-account method is established. Also pending before a public launch: email verification/recovery/deletion/export, shared rate limits, backups/restores, and independent security/licensing reviews. Keep registration disabled.


## Completed work step — PostgreSQL integration coverage added

Date: 2026-10-16

- Added `backend/tests/test_postgres_integration.py` with real PostgreSQL coverage for stale-revision rejection without overwriting the latest snapshot, simultaneous first-time snapshot writes (one succeeds and the other receives HTTP 409), session sign-out/sign-in persistence, and per-account library isolation.
- Extended `.github/workflows/omnishelf-1-3-8-checks.yml` with a disposable PostgreSQL 16 service, migration application, and the integration test run. The test job uses only the ephemeral GitHub Actions database; it does not insert test accounts into the hosted Neon preview database.
- The first integration run exposed a test-client cookie setup mistake (the second client did not send the session cookie). Corrected the test to pass the same opaque session token explicitly to both concurrent requests; no application behavior or registration setting was changed to get tests passing.
- Latest check run **38851867171** succeeded across five jobs: backend tests, migration checks, free deployment safety guard, frontend desktop/mobile preview capture, and PostgreSQL integration tests. Run: https://github.com/Reisquin/Omnishelf/actions/runs/38851867171
- Latest live smoke run **38851867077** also succeeded against https://omnishelf-1-3-8-free.onrender.com: PostgreSQL-backed health endpoint, HTTPS security headers, auth response cache policy, registration still disabled (HTTP 403), root shell, no browser exceptions, no mobile horizontal overflow. Run and screenshot artifact: https://github.com/Reisquin/Omnishelf/actions/runs/38851867077
- Fresh deployed-service full-page screenshots were captured at that run and extracted as `OmniShelf_1.3.8_Latest_Live_Desktop_Preview.png` and `OmniShelf_1.3.8_Latest_Live_Mobile_Preview.png` in the current working session.
- The remaining gap is now specifically authenticated end-to-end testing on the hosted Render + Neon pair. Registration remains disabled; do not open it merely to run tests. Establish a controlled test-account setup first.


## Completed work step — Render port-binding fix and post-deploy verification

Date: 2026-10-16

- Investigated the stuck cleanup deployment. Render eventually marked deployment `dep-db8r1g6i0phs738nckq0` failed with “Port scan timeout reached, no open ports detected.” The build had succeeded, but it was not safe to claim the cleanup commit was live.
- Identified a configuration mismatch: Dockerfile declared `EXPOSE 8000` while Render assigned `PORT=10000` and Uvicorn logs showed it listening on 10000.
- Corrected `Dockerfile` to `EXPOSE 10000` and `--port ${PORT:-10000}`; added a CI guard for exposed port 10000, binding to `0.0.0.0`, and respecting Render's `PORT`.
- Fix commit: `0ece07a50f900190e7e4db7bbc4a87e031ae62b8` ([view commit](https://github.com/Reisquin/Omnishelf/commit/0ece07a50f900190e7e4db7bbc4a87e031ae62b8)).
- Render deployment `dep-db8rc5cs728c73aq5rp0` reached `live` at 2026-10-16 05:29:40 UTC; logs confirm the new instance was listening on `0.0.0.0:10000`.
- Latest CI run `38855953255` passed all five jobs, including the new port configuration guard: https://github.com/Reisquin/Omnishelf/actions/runs/38855953255.
- Re-ran live smoke workflow `38855953928` as attempt 2 **after** deployment succeeded; it passed PostgreSQL-backed health, HTTPS/HSTS and `nosniff`, auth cache protection, anonymous cloud-state 401, registration-disabled 403, app root 200, and browser checks. Run: https://github.com/Reisquin/Omnishelf/actions/runs/38855953928.
- Fresh full-page deployed UI screenshots captured after deployment: `OmniShelf_1.3.8_Post_Deploy_Live_Desktop_Preview.png` and `OmniShelf_1.3.8_Post_Deploy_Live_Mobile_Preview.png` (retained in GitHub artifact `omnishelf-1.3.8-live-acceptance`, artifact ID `12026513359`, until 2026-10-30).
- The temporary QA route stays removed, its Render token remains empty, public registration stays disabled, and the Neon tables `users`, `sessions`, and `state_snapshots` were verified empty after cleanup.
- Still pending: full authenticated hosted test (secure cookie, cloud save/read across sign-out/sign-in, stale revision, concurrent first save, two-account isolation). Database/session variants pass against disposable PostgreSQL in CI; the hosted authenticated flow has not yet been proven. Keep registration closed. Also pending before public launch: email recovery/verification/deletion/export, shared rate limiting, backup/restore drill, security review, licensing review.


## Completed work step — production-mode PostgreSQL authentication coverage

Date: 2026-10-16

- Added `test_postgres_https_login_works_while_registration_is_closed` to the disposable PostgreSQL integration suite.
- This test provisions accounts only through the fixture's temporary registration-enabled mode in GitHub Actions, then switches registration off and Secure cookies on before exercising actual FastAPI HTTP routes over HTTPS TestClient.
- It verifies Secure/HttpOnly/SameSite=Lax cookies, HSTS, `Cache-Control: no-store`, allowed sign-in while registration is disabled, snapshot save/read, stale-revision 409 without overwriting, logout/session revocation, restore after sign-in, and another existing account's empty library.
- No hosted Neon rows or public registration settings were modified. This improves production-mode confidence but does not substitute for the still-pending end-to-end test against the hosted Render + Neon service.

- **Verification outcome:** CI run `38856765191` passed all five jobs, including PostgreSQL production-mode authentication with registration disabled. Live smoke run `38856765111` also passed and captured fresh desktop/mobile screenshots after the port fix. Artifact ID `12027606745` remains available until 2026-10-30.
- **Hosted data remains untouched:** read-only Neon counts after the run were `users=0`, `sessions=0`, and `state_snapshots=0`; only the `alembic_version` marker remains.

## Completed work step — browser-level cloud-sync UI acceptance

Date: 2026-10-16

- Added a Playwright acceptance script for the account/cloud-sync interface and wired it into the build-preview workflow.
- The browser test signs in to a local mocked account, completes the first-upload flow, simulates a competing remote save and verifies the stale upload is blocked, restores the newer cloud copy, then signs out and verifies local data remains persisted in the browser.
- The test uses a local mocked API only. It neither connects to hosted services nor creates or changes any hosted account/library data.
- Verified: GitHub Actions run 38860148427 passed all five jobs, including PostgreSQL integration tests and the new cloud-sync browser journey.
- Fresh build screenshots are in the workflow artifact omnishelf-1.3.8-layout-previews (artifact ID 12028942100; available through 2026-10-30): desktop, mobile, and the connected account/cloud-sync panel.
- This is frontend regression coverage, not proof of authenticated hosted persistence. The remaining hosted Render + Neon authenticated acceptance test, backup/restore drill, account recovery features, rate-limit hardening, security review, and licensing review remain open. Keep registration disabled.

## Completed work step — isolated hosted authentication staging lane

Date: 2026-10-16

- Added a separate Neon branch, auth-staging-2026-10-16 (br-tiny-moon-ao9v8tny), and a separate Render Free service, https://omnishelf-1-3-8-auth-staging.onrender.com (service ID srv-db8s513bc2fs73c0a9v0).
- The staging service points only to its isolated database branch. HTTPS-only cookies stay enabled and public registration remains disabled; the primary Neon branch and original 1.0.0 service are untouched.
- Read-only verification of the staging database returned zero users, zero sessions, zero snapshots, and migration 001_initial_backend present.
- Staging smoke workflow run 38860955820 passed, including live Postgres health, security headers, anonymous-state denial, closed registration, desktop/mobile browser rendering, and screenshot generation. The same run passed the existing full preview smoke job.
- Fresh screenshots: artifact omnishelf-1.3.8-auth-staging-previews, ID 12028079809, available until 2026-10-30. Desktop and mobile PNGs were downloaded to the working session.
- Remaining gate: authenticated HTTP E2E against this new staging URL. That run must create an ephemeral random-password account only in the staging branch, verify Secure/HttpOnly/SameSite cookies, persist and restore a snapshot across login/logout, confirm 409 stale-write protection and two-account isolation, and clean up only its own rows. Do not open registration or commit credentials to the public repo. No staging test accounts were seeded in this step.

### Current next action

Implement and run a controlled, self-cleaning authenticated acceptance runner for the isolated staging service. Keep the task explicitly marked pending until that runner reports a successful authenticated end-to-end result. Afterward, the next production-readiness work remains backup/restore verification, account verification/recovery/deletion/export, shared rate limiting, independent security review, and data-source/licensing review.

## Completed work step — authenticated hosted staging acceptance

Date: 2026-10-16

- Added a staging-only account bootstrap/cleanup hook that is disabled unless OMNISHELF_STAGING_ACCEPTANCE_ENABLED=true on the dedicated staging service. It requires a signed short-lived GitHub Actions OIDC token with the expected issuer, audience, repository, branch ref, workflow file, and push event; it fails closed if the configured staging origin or HTTPS/registration settings do not match.
- Added scripts/live_staging_auth_acceptance.py and a workflow job with id-token permission only for the staging acceptance job. The runner creates random passwords at runtime, does not log them, and invokes cleanup in a finally block. No passwords or database connection strings are stored in source.
- Passed the real hosted authenticated test: workflow run 38862355701. It created two temporary accounts and verified secure session-cookie flags, closed public registration, simultaneous first-save concurrency (one HTTP 200 and one 409), stale revision rejection without overwrite, logout/session revocation, snapshot persistence after a fresh login, and isolation between two accounts.
- The run's cleanup removed both temporary accounts. Read-only checks confirmed both the dedicated staging branch and primary preview branch now have zero users, zero sessions, and zero state snapshots; migration 001_initial_backend remains present.
- Preview-route exposure is guarded: the staging hook is mounted only when the staging service explicitly enables it, while the normal free blueprint omits the flag. CI tests the default-off mode and the live preview smoke job confirms the staging-only route is unavailable there.
- Passed CI run 38862355750 (all five jobs). Staging and ordinary preview live smoke jobs both passed in run 38862355701.
- Fresh live screenshots are in workflow artifacts omnishelf-1.3.8-auth-staging-previews (ID 12029526545) and omnishelf-1.3.8-live-acceptance (ID 12029118953), available until 2026-10-30.
- The hosted authentication milestone is now closed. Remaining before public launch: account verification/recovery/deletion/export, shared rate limiting and abuse controls, database backup/restore drill, independent security review, and data-provider/licensing review. Public registration remains disabled.

## Completed work step — backup/restore drill and CI regression test

Date: 2026-10-16

- Added scripts/backup_restore_drill.py to the PostgreSQL integration job. It writes a non-login canary user and snapshot into the disposable CI database, creates a PostgreSQL custom-format logical backup, restores it to a newly created database, and verifies the migration marker, application tables, foreign-key constraint, account identity, snapshot revision, and exact work payload. The restore target is dropped automatically; the generated archive stays inside the ephemeral CI runner.
- The new data-bearing drill passed with all five CI jobs in [run 38864850286](https://github.com/Reisquin/Omnishelf/actions/runs/38864850286). Backup archive size was 7,233 bytes; restored canary snapshot revision was 42.
- Created manual Neon snapshot snap-nameless-thunder-ao24daoi from the original primary branch and restored it to separate branch br-holy-meadow-aoztug2u. Both the original main and recovered branch report zero users, sessions, and snapshots, with migration 001_initial_backend applied. The native snapshot therefore proves the baseline schema/migration recovery; the CI pg_dump/pg_restore test proves recovery of non-empty user/library rows.
- Neon rejected creation of an automatic snapshot schedule for this project (“backup schedule creation is not enabled for this project”). The manual snapshot expires 2026-10-30 and should not be treated as recurring protection.
- One isolated drill-source branch, backup-restore-drill-source-2026-10-16 (br-old-violet-aoe919fi), retains one synthetic non-login canary account and snapshot as evidence; no live service uses it. It was not deleted because destructive branch/data deletion requires explicit approval.
- Latest live preview smoke passed in [run 38864850271](https://github.com/Reisquin/Omnishelf/actions/runs/38864850271); fresh desktop/mobile previews are available in artifact omnishelf-1.3.8-live-acceptance, ID 12030607732, through 2026-10-30.
- Remaining: enable a recurring backup strategy when project permissions/plan allow it, and later run a recovery test from that recurring schedule. Registration remains disabled pending account recovery/export/deletion, abuse-control, security, and licensing work.

## Completed work step — account data export and password-confirmed deletion

Date: 2026-10-16

- Added GET /api/me/export to produce a downloadable JSON export containing the caller's account metadata and saved cloud library. It omits password hashes and session/token secrets and sets a no-store attachment response.
- Added DELETE /api/me/account, requiring an accepted Origin and correct current password. It removes the account, saved cloud snapshot, and all sessions, expires the current session cookie, and leaves local browser data untouched.
- Added “Download my account data” and “Delete account” controls to the account/cloud-sync panel. The UI downloads the JSON file and requires both an explicit permanent-deletion confirmation and password prompt.
- API tests cover export content/secrecy, wrong-password rejection, current account/session removal, revocation of a second session, and denial of cloud access after deletion. PostgreSQL integration repeats export/deletion against the disposable PostgreSQL service. Playwright tests cover the download, deletion prompt, and local-library retention.
- Real hosted tests passed in [run 38866747552](https://github.com/Reisquin/Omnishelf/actions/runs/38866747552): exported library contents verified without secrets; wrong password rejected; correct password removed account two and revoked its other session; account one's data stayed intact. The OIDC-protected cleanup removed the other temporary account after the test.
- Five-job CI passed in [run 38866747602](https://github.com/Reisquin/Omnishelf/actions/runs/38866747602). Both isolated 1.3.8 deployments are live on commit bb61134d992ec895c1f98c441f4b8286dbde7ea7; original 1.0.0 release remains untouched. Read-only database checks confirmed no user/session/snapshot rows remain in primary or staging.
- Fresh screenshots: artifact omnishelf-1.3.8-auth-staging-previews (ID 12031282360), omnishelf-1.3.8-live-acceptance (ID 12030914679), and omnishelf-1.3.8-layout-previews (ID 12031442078), available through 2026-10-30.
- Remaining pre-launch blockers: email verification, password recovery, shared rate limiting/abuse controls, recurring backups/retention (Neon schedule creation is disabled for this project), independent security review, and provider/licensing review. Registration remains disabled.

## Completed work step — shared authentication rate limiting

Date: 2026-10-16

- Replaced the process-local rate limiter with an atomic, database-backed fixed-window counter shared across application workers and instances.
- Limits: 5 registration attempts per client address per hour; 10 login attempts per client address per 15 minutes. The endpoint returns 429 and Retry-After when exceeded; the counter is capped at limit+1 and old records are opportunistically purged.
- Raw IP addresses are not stored: the limiter stores an HMAC. The stable hash key is configured by RATE_LIMIT_HASH_KEY, with shared DATABASE_URL as the fallback so workers attached to the same database agree. In Render's hosted environment, the client IP resolver uses the first platform-provided X-Forwarded-For entry; local runs ignore forwarded headers.
- New Alembic migration: 002_shared_auth_rate_limits. API tests cover shared counters, first-client-IP selection for Render forwarding headers, and expired-window reset; PostgreSQL integration sends 8 simultaneous attempts across separate clients and confirms 3 reach credential verification while 5 receive 429.
- All five jobs passed in CI run 38870722468. Source commit 2eecb50ef2868f2e9c17dfc4f294953a70bf4ccf is deployed to the isolated 1.3.8 staging and preview services. Post-deployment live acceptance passed in run 38871388659 after deployments completed.
- This closes the shared IP-based login/registration throttle baseline; additional abuse controls still remain. Public registration remains disabled.

- Deployment verification caveat: staging's Neon branch confirms migration 002, and the preview service's PostgreSQL startup logs show that Alembic ran the same upgrade. A direct query to the known Neon project's primary branch still reports 001 and no auth_rate_limits table, so the preview service's exact DATABASE_URL target remains unverified. Confirm the service-to-database mapping before using Neon main as the preview's backing store. Do not change the connection string blindly.
- Fresh post-deployment screenshot artifacts are auth staging previews ID 12033323664, live screenshots ID 12033277508, and layout previews ID 12032499043, retained through 2026-10-30.


## Feature build 1.3.9 — email verification and password recovery
Date: 2026-10-18

- Created isolated branch `feature/1.3.9-email-verification-password-reset` from the accepted 1.3.8 HTTPS preview. This is a code branch only: it has not been merged or deployed, and the 1.3.8 live service remains unchanged.
- Added migration `003_email_verification_and_reset`: records an email-verification timestamp, marks accounts created before this feature as verified so existing logins survive, and adds a token table with single-purpose hashes, expiry, and cascading account deletion.
- Added account verification, resend-verification, password-reset request, and password-reset confirmation endpoints. Verification/reset tokens are random, stored as SHA-256 hashes, expire (24h/30m defaults), and are serialized with a row lock when consumed. Password recovery changes the Argon2 hash and revokes all server sessions.
- Added rate-limit buckets for verification and reset requests/actions; generic request responses avoid revealing whether an email belongs to an account. Hosted mail requires STARTTLS, a configured sender, and the trusted HTTPS `PUBLIC_APP_ORIGIN`. If mail is not configured, signup/recovery fails closed; hosted public registration remains disabled.
- Added sign-in UI links for forgotten passwords and resending verification email, a reset-password form, email-link handling, API tests using a mocked mail sender, PostgreSQL integration coverage, and Playwright UI coverage. The build version and desktop/mobile screenshot artifact labels are 1.3.9.
- Validation status at note creation: source and CI configuration committed on the feature branch, but CI has not yet been reported green. Do not call this release-ready until the pull-request checks and screenshot artifact succeed.
- Remaining before any deployment: configure and test an SMTP sender in secret settings; verify the preview service's real Neon target instead of assuming it is the currently listed primary branch; reconcile migration target; retain public registration disabled; then complete backup-retention, independent security and provider/licensing reviews.


## Validation follow-up — OmniShelf 1.3.9
Date: 2026-10-18

- GitHub Actions run [39072395285](https://github.com/Reisquin/Omnishelf/actions/runs/39072395285) passed all five jobs on revision `36cd170800141742f785f58379cc8452f71a5dad`: frontend/layout preview, isolated API tests, PostgreSQL integration tests, free deployment configuration, and fresh SQLite migration check.
- The same run produced artifact `omnishelf-1.3.9-layout-previews`, including desktop/mobile profile shots, the sign-in recovery links, password-reset form, and connected cloud-sync screen. Artifact expires 2026-10-31.
- The subsequent cleanup only removed temporary diagnostics from the browser test. Its new HEAD must have its own green check before merge.
- The browser/API tests use a mocked mail sender; real SMTP delivery and trusted-origin settings are not yet validated in the hosted service. No live service, branch deployment, or hosted database was changed. The 1.3.9 PR remains a draft pending SMTP setup, database-target reconciliation, and launch review.


## Recovery endpoint privacy hardening
Date: 2026-10-18

- Updated email-verification resend and password-reset requests so SMTP delivery errors do not change the public response. Known and unknown addresses now receive the same generic HTTP 202 response, removing a response-status/detail side channel that could disclose account existence.
- Delivery failures produce fixed, non-sensitive warning messages; exception text, recipients, and email tokens are not written to the application log.
- Added regression tests that simulate SMTP failures for both existing and nonexistent addresses and assert identical status codes and response bodies.
- This is still an isolated feature-branch change. It has not been deployed to the 1.3.8 preview, and public registration remains disabled. The updated CI results and refreshed screenshot artifacts should be recorded only after the new branch HEAD passes.


### Validation result — recovery privacy hardening
Date: 2026-10-18

- **Passed:** GitHub Actions run [39075433434](https://github.com/Reisquin/Omnishelf/actions/runs/39075433434) on revision `b9e05b23d6f9e57a2865a1b3a5a74b083309b0a5`; all five jobs passed, including the newly added mocked-SMTP failure regression tests.
- **Fresh preview artifact:** `omnishelf-1.3.9-layout-previews`, artifact ID `12117200332`, includes desktop, mobile, connected cloud-sync, sign-in recovery links, and password-reset form screenshots; retained through 2026-10-31.
- The change remains on the draft 1.3.9 feature branch. It does not alter live services or enable public registration.
- Remaining before a hosted 1.3.9 rollout: configure SMTP credentials/sender through secret settings and verify real email delivery; resolve which Neon database each 1.3.8 service actually uses before applying migration 003; keep public registration closed until provider delivery, backup-retention, independent security, and provider/licensing reviews are complete.


## Next launch-readiness step — SMTP transport acceptance
Date: 2026-10-18

- Added mocked SMTP transport regression tests to prove message delivery uses STARTTLS with certificate validation, performs configured authentication, and refuses delivery if STARTTLS is disabled. These checks avoid contacting any external mail server or using real credentials.
- Expanded the 1.3.9 README with secret-setting guidance and a pre-launch SMTP acceptance checklist covering real mailbox verification, one-time-link replay, session revocation, generic request responses, and read-only migration-target verification.
- The feature branch has not been deployed. Real SMTP settings still require a mail provider sender/credentials in Render's private environment settings; no credentials were invented or written into source. Public registration stays disabled.
- Database mapping remains unresolved: the 1.3.8 free service logs show Alembic revision 002 applied, while the Neon primary branch queried through the available account connection shows revision 001 and the isolated auth-staging branch shows revision 002. Render's available metadata does not reveal the secret database URL, so do not repoint services or apply migration 003 until an authorized in-service target check is available.
- Independent security review, recurring backup-retention strategy, and provider/licensing review remain required before public launch.


### SMTP transport gate — validation result
Date: 2026-10-18

- **Passed:** GitHub Actions run [39075898791](https://github.com/Reisquin/Omnishelf/actions/runs/39075898791), revision `519bda67621b98fca0e12d069300ff8f2fad21d6`; all five jobs passed after adding mocked SMTP STARTTLS/authentication tests and the SMTP acceptance checklist.
- **Fresh layout artifact:** `omnishelf-1.3.9-layout-previews`, artifact ID `12117265981`, includes updated desktop/mobile and account recovery screens. The frontend itself was not changed in this documentation/test-only step.
- This verifies transport behavior against a mocked SMTP client. It does not verify a real provider, credentials, sender-domain authentication, or delivery to a real mailbox. Those remain a deployment gate.
- Existing hosted 1.3.8 services remain unchanged; migration 003 has not been applied to them.

## Hosted email configuration preflight
Date: 2026-10-18

- Added `backend/config_preflight.py`, a no-network command that validates required SMTP settings, a valid SMTP port, HTTPS-only `PUBLIC_APP_ORIGIN`, STARTTLS, mandatory email verification, Secure cookies, and closed public registration.
- The command `python -m backend.config_preflight` reports only setting names and policy failures; it never prints environment values. It explicitly says that SMTP connectivity and actual mailbox delivery are not tested.
- Added `backend/tests/test_config_preflight.py` to cover valid hosted configuration, missing secret handling, unsafe flags/invalid origins, and protection against printing sensitive environment values. These tests are included in the existing backend test job.
- This is a source/CI safeguard only. No Render environment variables, database targets, migrations, or hosted services were changed. The real SMTP-provider mailbox test and database-target reconciliation remain deployment blockers; public registration remains disabled.
- Next: verify this branch revision's five CI jobs and regenerate the 1.3.9 screenshot artifact; then continue isolated staging acceptance without merging or changing the live preview.

### Hosted email preflight — validation result
Date: 2026-10-18

- **Passed:** GitHub Actions run [39153980909](https://github.com/Reisquin/Omnishelf/actions/runs/39153980909) on the 1.3.9 feature branch. All five jobs passed: backend tests (including the new preflight tests), PostgreSQL integration tests, free-deployment configuration guard, Alembic migration check, and Playwright layout preview.
- **Fresh visual artifact:** `omnishelf-1.3.9-layout-previews`, artifact ID `12145269780`, containing desktop, mobile, sign-in recovery, password-reset, and cloud-sync screenshots.
- The preflight checks required setting presence, port bounds, HTTPS-origin structure, STARTTLS, verification, Secure cookies, and disabled registration; regression tests check it never prints configured values. It does not test SMTP connectivity or real message delivery.
- Source remains isolated on `feature/1.3.9-email-verification-password-reset` and PR #1 remains a draft. No hosted service, production branch, environment variables, or database was changed. Migration 003 is not applied to hosted databases by this step.
- Next gate remains real SMTP acceptance on a dedicated mailbox and a safe read-only reconciliation of the Render service's configured database target before any deployment. Keep public registration disabled.

## Hosted database target guard
Date: 2026-10-18

- Added `backend/database_target_preflight.py`, a read-only pre-migration target check. On Render it requires `OMNISHELF_EXPECTED_DATABASE_HOST` and `OMNISHELF_EXPECTED_DATABASE_NAME`, compares them to the non-secret target fields in `DATABASE_URL`, then queries the connected database name and currently applied Alembic revision.
- Updated the Docker startup command to run the guard **before** `alembic upgrade head`. Missing/mismatched settings or a failed identity query stop startup before migrations run. Local development bypasses this hosted-only guard.
- Diagnostics never print the connection URL, username, or password; mismatch output suppresses the actual connection target. On success, only the confirmed hostname, database name, and revision are shown.
- Added tests for host/database mismatch rejection, no connection on a pre-connection mismatch, read-only revision identification, connected database mismatch, local-development skip, and secret non-disclosure. The deployment-configuration CI job now checks the ordering of the guard and Alembic command.
- **Passed:** GitHub Actions run [39154625201](https://github.com/Reisquin/Omnishelf/actions/runs/39154625201) on source/docs revision `eb9b1605565bdf40dc71c8904a4130f9972e599b`; all five jobs passed.
- **Fresh visual artifact:** `omnishelf-1.3.9-layout-previews`, artifact ID `12146960747`, containing desktop/mobile profile layouts and the account recovery/cloud-sync screens.
- This change makes no hosted service/database changes and does not apply migration 003 anywhere. The PR remains a draft. Before any hosted deployment, independently confirm the intended Neon target and set the two expected-target values in the intended service's private settings; real SMTP delivery, backups/restore, independent security review, and provider/licensing review remain release blockers. Keep public registration disabled.

