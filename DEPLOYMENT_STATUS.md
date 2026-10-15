# OmniShelf 1.3.8 deployment status

## Current public preview

- Frontend-only HTTPS preview: https://omnishelf-1-3-8-preview.onrender.com
- The preview is for visual inspection. Accounts and cross-device cloud synchronisation are not yet connected.
- Latest pre-deployment CI passed on 2026-10-15. The desktop/mobile visual previews remain the latest captured layout checks.

## Free-first cloud preview — prepared, not yet deployed

- Repository: https://github.com/Reisquin/Omnishelf
- Branch: `deploy/1.3.8-https-preview`
- Free-only Render configuration: [`render.free.yaml`](https://github.com/Reisquin/Omnishelf/blob/deploy/1.3.8-https-preview/render.free.yaml)
- Step-by-step instructions: [`FREE_DEPLOYMENT_GUIDE.md`](https://github.com/Reisquin/Omnishelf/blob/deploy/1.3.8-https-preview/FREE_DEPLOYMENT_GUIDE.md)
- Proposed architecture: one Render **Free** Docker web service plus Neon **Free** PostgreSQL. The free blueprint deliberately defines no Render-hosted database.
- Registration remains `REGISTRATION_ENABLED=false`; Secure cookies remain enabled.
- The free blueprint asks for `DATABASE_URL` as a Render dashboard secret. A Neon pooled PostgreSQL URI must be created and stored there, not committed to the repository or pasted into chat.
- CI now validates that the free blueprint has exactly one service, selects plan `free`, creates no Render database, keeps the database URI secret, and leaves registration disabled.

## Billing and safety

- No new Render service or database has been created by this free-first preparation. No paid resource has been created.
- The original paid configuration remains in root `render.yaml` for an optional future upgrade only. Do not use that blueprint for the free-first deployment.
- The existing `main` branch and 1.0.0 service remain untouched.
- Render Free web services sleep after 15 minutes idle, may take roughly a minute to wake, and use ephemeral local storage. Therefore, all lasting state must be stored in the external PostgreSQL database. Render's free-tier traffic/build allowances also apply.
- Render Free PostgreSQL is intentionally not used because Render documents a 30-day expiry and no backups for the Free database plan.
- Remaining account-bound steps: select/confirm the Render workspace; create a Neon Free project and keep the pooled connection URI secret; create the Render service using `render.free.yaml`; then run the live acceptance checklist.
- Do not attach paid plans/add-ons or accept a charge prompt. If the service setup unexpectedly asks for payment or a paid plan, stop.

## Acceptance checks still pending

- [x] Free-first CI blueprint validation passes (CI run 38825891605).
- [ ] Deployed `GET /healthz` returns HTTP 200 and database status `ok`.
- [ ] PostgreSQL Alembic migrations complete.
- [ ] Secure session-cookie attributes are confirmed over HTTPS.
- [ ] Registration endpoint continues to return 403.
- [ ] Snapshot persistence, stale-revision handling, and two-account isolation pass.
- [ ] Desktop/mobile checks and screenshots are captured from the exact deployed commit.
- [ ] Free-tier usage is checked; no paid resource is present.

## Before public launch

Email verification, password recovery, account deletion/export, shared rate-limiting/abuse controls, database backup and restore testing, and independent security plus provider/licensing review remain requirements. Do not enable public registration until these are complete.
