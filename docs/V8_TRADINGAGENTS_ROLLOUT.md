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

## Signal and execution safety

TradingAgents emits a five-tier research rating. V8 maps Buy/Overweight to BUY, Sell/Underweight
to SELL, and Hold/REVIEW/unrecognized output to NO TRADE. A rating is not an executable order:
this integration deliberately does not fabricate entry, stop-loss, take-profit, position size, or
leverage. A separate deterministic risk-plan validator and exchange-specific Paper Trading adapter
must pass tests before any signal is considered execution-ready.

Hummingbot/live exchange execution is not enabled by this change. No exchange API key is required
for the research job queue, and no live order can be placed by this worker.

## Current rollout status

1. Source integration and API job contract: implemented in this branch.
2. Unit/API tests and worker image build: must pass in CI.
3. Vercel preview deployment: must be checked after CI.
4. Persistent worker host, durable storage, shared database, and model provider credentials:
   operator configuration still required before real agent runs.
5. Android dashboard consumption and Hummingbot Paper Trading adapter: follow-up integration.
