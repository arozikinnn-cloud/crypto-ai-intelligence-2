# API foundation

Base prefix: `/api/v1`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service metadata |
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/health/ready` | Readiness plus database connectivity |

Interactive OpenAPI documentation: `/docs`. No trading, account, or exchange credential endpoints are exposed in Phase 1.
