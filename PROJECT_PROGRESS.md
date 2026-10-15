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
- Latest known branch commit at this checkpoint: `b3faa2fc957b0251e488fbb90bd267af1b9060fe` (2026-10-15), “Label hosted frontend as preview while backend awaits billing setup.”
- Latest known `main` branch commit in the connected repository is `af5698fe1ba902d65e45028615060f9291332f3f` (2026-10-07); `main` contains the 1.0.0 archive. The 1.3.8 branch is kept separate.

### Known limitations/blockers
- The 1.3.8 public preview is **frontend-only**: cloud accounts and cross-device synchronisation are not connected on that deployment; browser-local features can work.
- The deployment record says provisioning managed PostgreSQL returned Render HTTP 402 because billing/payment details were required. No separate paid backend web service or managed database was created according to that record.
- Deployment acceptance checks remain open: database health, migrations, secure session-cookie checks, registration disabled, snapshot persistence after redeploy/sign-out/sign-in, stale-revision handling, isolation between test accounts, frontend console checks on desktop/mobile, and screenshots from the exact deployed commit.
- Public launch still requires email verification, password recovery, account deletion/export, shared rate limiting and abuse prevention, backups/restore testing, security review, and provider/licensing review.
- Keep public registration disabled until these issues are addressed. Do not claim cloud persistence, account isolation, or production readiness without passing the respective tests.

## Next actions

1. Confirm the intended Render workspace/service context before any cloud-resource changes. Do not select a workspace or create paid services without appropriate user confirmation.
2. Prepare and run local tests for the backend, migrations, auth/session behaviour, snapshot revision conflict handling, and account-data isolation.
3. Resolve billing/hosting prerequisites before attempting the separate PostgreSQL-backed preview deployment.
4. Deploy the backend only as a separate service, preserving the existing 1.0.0 service and `main` branch.
5. Run the deployment acceptance checklist and capture screenshots of the exact preview build.
6. Only then evaluate public-launch readiness and registration requirements.

## Work step in progress — backend verification harness

Date: 2026-10-16

- Added `backend/tests/test_api.py` with isolated SQLite-backed API tests covering version/health response and safety headers, disabled registration, user/email normalization, HttpOnly/SameSite session cookie attributes, duplicate identity rejection, origin validation, cloud-state round trips, revision-conflict protection, account-to-account snapshot isolation, invalid state shape, and logout/session revocation.
- Added `.github/workflows/omnishelf-1-3-8-checks.yml` with three jobs: API tests, fresh-database Alembic migration check, and desktop/mobile layout-preview image capture as a CI artifact.
- Source files exist on the isolated 1.3.8 branch. The GitHub Actions API currently reports no workflow runs, so no automated test, migration, or CI screenshot result is claimed yet. A successful run remains required before considering this step validated.
- No Render resources were created and no paid deployment was attempted. The existing `main` branch and 1.0.0 service are intended to remain untouched.
- Preview for this turn: the documented frontend URL remains https://omnishelf-1-3-8-preview.onrender.com. A separate static visual layout reference will be shown alongside it because the live page was not accessible to the browser tool in this session.
- Next: obtain a real CI run, address any failures, review the screenshot artifact, then proceed to backend deployment readiness without enabling public registration.

## Working rule for future turns

After each meaningful project step:
- update this log with the version, changed files, decisions, test results, blockers, and next action;
- preserve earlier milestones and user requirements;
- distinguish source code, local test results, preview deployment, verified cloud persistence, and production launch as separate states;
- include a screenshot/visual preview for every build/update where feasible;
- never describe an unverified build, deploy, integration, or test as completed.
