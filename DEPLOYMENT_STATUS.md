# OmniShelf 1.3.8 deployment status

## Public preview

The frontend-only HTTPS preview is deployed at:

- https://omnishelf-1-3-8-preview.onrender.com

This is a static preview for inspecting the 1.3.8 UI. Browser-local features work, but cloud accounts and shared storage are unavailable on this frontend-only preview because its `/api` endpoints are not attached to a backend yet.

## Isolated backend deployment branch

- Repository: https://github.com/Reisquin/Omnishelf
- Branch: `deploy/1.3.8-https-preview`
- Source: root `index.html`, `backend/`, `Dockerfile`, and `.dockerignore`
- The existing `main` branch and existing 1.0.0 Render service have not been modified.

## Blocker for cloud backend

Creating a paid managed Postgres resource returned Render API HTTP 402: payment information is required. No database or paid web service was created. After a payment method is added, the included `render.yaml` can create the separate $7/month web service and $6/month managed Postgres (about $13/month before usage overages).

The deployment blueprint deliberately keeps `REGISTRATION_ENABLED=false` for a controlled preview. Public registrations should not be opened until email verification, password recovery, account deletion/export, shared abuse controls and security review are ready.
