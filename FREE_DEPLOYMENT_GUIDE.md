# OmniShelf 1.3.8 — Free-first preview deployment

## Target architecture

- **Web/API:** One Render Free Docker web service, using `render.free.yaml`.
- **Database:** One Neon Free PostgreSQL project. Do **not** add a Render Postgres database to this preview.
- **Registration:** Disabled. Keep `REGISTRATION_ENABLED=false` throughout controlled testing.
- **Existing launch:** The 1.0.0 service and `main` branch remain untouched.
- **Paid upgrade:** `render.yaml` is preserved for a separately approved future upgrade; do not use it for the free-first deployment.

## Important free-tier trade-offs

Render's free web service sleeps after 15 minutes without inbound traffic; waking can take about a minute. Its local filesystem is ephemeral, so application state must live in PostgreSQL. Free Render Postgres is deliberately not used here because it expires after 30 days and has no backups. Render may suspend a free web service if it initiates unusually high external traffic, including external-database access. This free architecture is for a controlled preview and testing, not a production launch.

Neon's Free plan currently advertises 1 GB of storage per project. Free-tier quotas and provider terms can change. Keep both providers on their Free tiers and monitor usage.

## Database setup (Neon)

1. Create a Neon account/project named `omnishelf-preview` and select the Free plan. Choose Singapore / `ap-southeast-1` if offered, to keep the database near the Render service.
2. Create or use the project's default database and copy its **pooled** PostgreSQL connection string. Keep SSL enabled (the generated URI normally includes `sslmode=require`).
3. Treat the URI as a password: never commit it to GitHub, put it in screenshots, or paste it into chat. Use it only as Render's secret value for `DATABASE_URL`.
4. The app's driver supports PostgreSQL URLs and uses the versioned Alembic migration at container start. The deployed `/healthz` endpoint should return `{"status":"ok","database":"ok","version":"1.3.8"}` only after a working database connection.

## Create the free web service (Render)

1. In the intended Render workspace, create a **Blueprint** from repository `Reisquin/Omnishelf`, branch `deploy/1.3.8-https-preview`.
2. Set the Blueprint file/path to `render.free.yaml` (not the default `render.yaml`). Before continuing, visually confirm there is exactly one web service, the service plan is **Free**, and no Render Postgres database is listed.
3. When prompted for the secret `DATABASE_URL`, enter the Neon pooled URI directly in Render's secret field. Do not put this URI into the repo.
4. Confirm the resulting service is named `omnishelf-1-3-8-free`, its deploy branch is `deploy/1.3.8-https-preview`, and registration remains disabled.
5. If Render asks for a paid plan, payment method, or charge approval, stop rather than accepting it. Do not add paid features or change the service/database tier.

This first-time Blueprint creation is a manual account-bound action; do not assume workspace selection or that a database URI exists until explicitly configured.

## Acceptance tests after deployment

- [ ] `GET /healthz` returns HTTP 200 and database status `ok`.
- [ ] Startup migrations succeed against Neon PostgreSQL.
- [ ] HTTPS session cookies are Secure, HttpOnly and SameSite=Lax.
- [ ] `POST /api/auth/register` returns 403 because registration remains disabled.
- [ ] Login, snapshot read/write, stale revision (409), and two-account isolation pass using controlled test accounts.
- [ ] State persists after sign-out/sign-in and a service redeploy.
- [ ] Desktop/mobile browser checks and screenshots are captured from this exact deployed commit.
- [ ] Free-tier usage is reviewed and no paid resource has been created.

## Useful provider documentation

- Render free services: https://render.com/docs/free
- Render Blueprint YAML: https://render.com/docs/blueprint-spec
- Render pricing/usage: https://render.com/pricing
- Neon Free plan: https://neon.com/blog/neon-free-plan-1-gb-per-project

Do not enable public registration until account verification/recovery/deletion/export, shared abuse protection, backups/restore, and independent security and provider/licensing reviews are complete.
