# API foundation

Base prefix: `/api/v1`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service metadata |
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/health/ready` | Readiness plus database connectivity |

Interactive OpenAPI documentation: `/docs`. No trading, account, or exchange credential endpoints are exposed in Phase 1.


## Analysis and evaluation endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/analysis/intelligence` | Multi-source technical, structure, order-flow, CVD, liquidation context and order-book snapshot confluence |
| GET | `/api/v1/analysis/order-book` | Current public Spot depth imbalance and spread snapshot |
| GET | `/api/v1/analysis/intelligence/backtest` | Combined rule-based historical simulation with train/OOS metrics |
| GET | `/api/v1/analysis/intelligence/timeframe-performance` | Compare strategy metrics across selected timeframes |

The order-book endpoint is a snapshot, not historical DOM or absorption detection. Backtest results do not replay historical CVD, liquidation, order-book, OI/funding, news, or sentiment.
