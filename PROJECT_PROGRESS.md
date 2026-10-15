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
- The 1.3.8 public preview is **frontend-only**: cloud accounts and cross-device synchronisation are not connected on that deployment; browser-local features can work.
- The deployment record says provisioning managed PostgreSQL returned Render HTTP 402 because billing/payment details were required. No separate paid backend web service or managed database was created according to that record.
- Deployment acceptance checks remain open: database health, migrations, secure session-cookie checks, registration disabled, snapshot persistence after redeploy/sign-out/sign-in, stale-revision handling, isolation between test accounts, frontend console checks on desktop/mobile, and screenshots from the exact deployed commit.
- Public launch still requires email verification, password recovery, account deletion/export, shared rate limiting and abuse prevention, backups/restore testing, security review, and provider/licensing review.
- Keep public registration disabled until these issues are addressed. Do not claim cloud persistence, account isolation, or production readiness without passing the respective tests.

## Next actions

1. Confirm the intended Render workspace/service context before any cloud-resource changes. Do not select a workspace or create paid services without appropriate user confirmation.
2. Resolve billing/hosting prerequisites and obtain explicit authorization before attempting the separate PostgreSQL-backed preview deployment.
3. Deploy the backend only as a separate service, preserving the existing 1.0.0 service and `main` branch.
4. Run the deployment acceptance checklist and capture screenshots of the exact preview build.
5. Only then evaluate public-launch readiness and registration requirements.

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
