# Crypto AI Intelligence V8 — TradingAgents rollout

## Decision

V8 replaces the former deterministic RSI/MA/Ichimoku signal decision engine with the upstream
Tauric Research TradingAgents multi-agent research graph. The upstream package is pinned to
commit `9fa1196fffbcfd9de5146d2dd2869df84ab99838` so worker builds are reproducible.

The API remains a lightweight FastAPI service. It accepts and stores analysis jobs; a separate
persistent Python worker claims jobs and runs TradingAgents. The heavyweight agent dependencies
are intentionally excluded from the Vercel API deployment.

## Job API

- `POST /api/v1/agent-analysis/jobs?symbol=BTCUSDT` — enqueue a research run.
- `GET /api/v1/agent-analysis/jobs/{id}` — read job status and result.
- `GET /api/v1/agent-analysis/jobs?symbol=BTCUSDT&limit=20` — list recent runs.

The enqueue endpoint returns HTTP 503 until `TRADINGAGENTS_ENABLED=true`. This is deliberate:
a queue without a running worker would leave requests pending indefinitely.

## Worker

Build from the `backend` directory:

```bash
docker build -f Dockerfile.agent-worker -t crypto-ai-agent-worker .
docker run --env-file .env -v tradingagents-data:/data crypto-ai-agent-worker
```

The API and worker must share the same durable PostgreSQL `DATABASE_URL`. The worker needs a
persistent process host and persistent `/data` storage if TradingAgents checkpoint/cache/memory
files are expected to survive restarts.

## Provider configuration

TradingAgents uses its upstream provider configuration. Configure one supported provider and its
required credential in the worker environment only (for example `OPENAI_API_KEY`,
`GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, or an Ollama/OpenAI-compatible endpoint). Never commit
provider credentials. Model API usage may incur charges; keep the feature disabled until the
operator has deliberately configured a provider and accepted its pricing.

Optional worker settings:

- `TRADINGAGENTS_OUTPUT_LANGUAGE=Indonesian`
- `TRADINGAGENTS_MAX_DEBATE_ROUNDS=1`
- `TRADINGAGENTS_MAX_RISK_ROUNDS=1`
- `TRADINGAGENTS_MAX_TOOL_ROUNDS=4`
- `TRADINGAGENTS_RESULTS_DIR=/data/tradingagents/results`
- `TRADINGAGENTS_CACHE_DIR=/data/tradingagents/cache`
- `TRADINGAGENTS_MEMORY_LOG_PATH=/data/tradingagents/memory/trading_memory.md`

## Bitget Futures market context and decision validation

The backend includes a read-only Bitget USDT-M Futures adapter using public endpoints (no exchange
API key is needed for market data). It fetches closed 5m, 15m, 30m, and 1h candles, an order-book
snapshot, open interest, and current funding rate. API routes:

- `GET /api/v1/market/bitget/candles?symbol=BTCUSDT&interval=15m&limit=200`
- `GET /api/v1/market/bitget/derivatives?symbol=BTCUSDT`
- `GET /api/v1/market/bitget/order-book?symbol=BTCUSDT&limit=100`

Before running the TradingAgents graph, the worker collects and validates Bitget data. A compact
exchange snapshot is injected into the instrument context passed to all analysts. The context
contains MA40, RSI16, ATR14, Ichimoku/Kumo, multi-timeframe direction, funding, open interest, and
order-book bid/ask notional imbalance. Upstream Yahoo Finance tools remain supplemental; they are
not treated as the source of exact futures prices.

A BUY/SELL plan is emitted only when the TradingAgents rating agrees with the 1h, 30m, and 15m
Bitget technical confirmation, and the 5m direction does not oppose it. Entry is the last closed
15m price; stop distance is 1.5 x ATR(14); target is 1.5R (risk/reward 1:1.5). Invalid, stale,
incomplete, or conflicting data produces NO TRADE. The result is never execution-ready.

## Forward signal journal

Validated V8 plans are persisted as V8-versioned signal events. The independent worker monitors
those plans against later closed 1m Bitget candles, while legacy signal events continue to use their
original Binance source. TP and SL touched in the same candle are conservatively counted as SL.
The dashboard's V8 signal history and win-rate endpoint filter to
`TRADINGAGENTS_MULTI_AGENT_V8` only. This is forward paper observation, not a historical
TradingAgents backtest and not proof of future profitability.

## Model provider and hosting requirements

TradingAgents still requires a supported model provider credential (for example OpenAI, Google,
Anthropic, or an OpenAI-compatible local endpoint). The credential must be configured privately
in the worker host. No provider key is present in the current Vercel project configuration.

The API and worker must share the same durable PostgreSQL `DATABASE_URL`. The worker also needs a
persistent process host and persistent `/data` storage. Vercel Functions are stateless and do not
keep this worker alive. The GitHub repository is public, but scheduled GitHub Actions are not a
true continuously running process and require securely configured worker/database/provider
secrets; they are not enabled as a substitute for a production worker.

## Free-tier scheduled execution (best effort, not 24/7)

A GitHub Actions workflow is included at `.github/workflows/tradingagents-v8-scheduled.yml`.
It runs one bounded TradingAgents job per invocation (scheduled every six hours, or manually
dispatched). It is an episodic runner, not a persistent worker, and it cannot guarantee exact
start times, continuous monitoring, or immediate push notifications. GitHub scheduled workflows
run from the default branch; while this PR is unmerged, use workflow_dispatch against the feature
branch for a controlled test.

To enable it, a repository administrator must add these Actions secrets under
Settings → Secrets and variables → Actions:

- `DATABASE_URL`: the same durable PostgreSQL connection string used by the Vercel API.
- `GOOGLE_API_KEY`: Gemini API key, stored only as an Actions secret.

The workflow validates that the database URL is PostgreSQL, queues BTCUSDT only when no job is
already pending/running, and processes at most one job per run. If either secret is absent, the
job skips safely. The workflow does not provision PostgreSQL, configure Vercel, or create secrets.
Do not enable it until a durable shared PostgreSQL database is available and the operator has
reviewed Gemini free-tier quotas and limits. A free Gemini quota is not a promise of unlimited use.

## Paper trading and execution safety

The project remains research/decision-support only. No live exchange order endpoint or Bitget
trading credential is configured. Hummingbot Paper Trade is not yet connected to this V8 pipeline;
the current forward signal journal only observes whether a plan's SL/TP would have been reached.
Do not call that a Hummingbot simulation or an execution test. A dedicated Hummingbot paper-trade
host/connector and integration tests are still required before considering the execution stage.

## Current rollout status

1. Backend Ruff/pytest, market-data worker image, and TradingAgents worker image: CI passing.
2. Flutter analyze, Flutter tests, and Android debug APK build: CI passing; the APK is available as a short-lived GitHub Actions artifact.
3. Vercel Preview API deployment: READY. It is a Preview deployment only; the long-running worker is not hosted there.
4. Shared durable PostgreSQL access for the worker, a persistent worker host/storage, and a model-provider credential are still missing.
5. Hummingbot Paper Trading is not integrated; the current signal journal is only a forward market-outcome tracker.
6. Historical TradingAgents backtest is not implemented. Keep the feature disabled and the PR unmerged until the remaining hosting/provider/security requirements and end-to-end tests are satisfied.
