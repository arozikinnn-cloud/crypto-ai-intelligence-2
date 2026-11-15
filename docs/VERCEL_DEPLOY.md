# Vercel deployment (serverless API)

This repository exposes the existing FastAPI application through `api/index.py`. Vercel detects the FastAPI app and routes requests to it.

## Vercel project settings

- Import `arozikinnn-cloud/crypto-ai-intelligence-2` from GitHub.
- Production branch: `deployment/vercel-serverless` while validating; merge to `main` only after successful tests.
- Root Directory: `.` (repository root).
- Framework preset: FastAPI / Other if automatic detection does not select FastAPI.
- Build command and Output Directory: leave unset unless Vercel requests otherwise.

## Required environment variables

Set these in Vercel Project Settings → Environment Variables. Use the existing Supabase PostgreSQL connection string as `DATABASE_URL`; do not commit it to GitHub.

- `APP_ENV=production`
- `DEBUG=false`
- `DATABASE_URL=<Supabase PostgreSQL connection string>`
- `CORS_ORIGINS=<allowed frontend origins, comma-separated>`
- `CVD_COLLECTOR_ENABLED=false`
- `LIQUIDATION_COLLECTOR_ENABLED=false`

The two collectors are deliberately disabled on Vercel: serverless functions are request-driven and are not a continuously running WebSocket worker. Their historical collection requires a separate always-on worker or scheduled ingestion design, which is not part of this deployment.

## Verify after deployment

- `/` should return the service status.
- `/api/v1/health` should return liveness.
- `/api/v1/health/ready` should confirm database readiness.
- `/docs` should load the OpenAPI documentation.

Do not add exchange API secrets for this read-only deployment. Never enable live order execution as part of deployment validation.

## Cost and plan

Use Vercel Hobby only for personal, non-commercial use and stay within its published quotas. No paid upgrade or payment method is authorized for this project. If Vercel requests payment details or an upgrade, stop and report it; do not enter a card.
