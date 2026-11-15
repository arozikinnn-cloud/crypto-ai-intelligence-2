from fastapi import APIRouter
from app.api.analysis import router as analysis_router
from app.api.backtest import router as backtest_router
from app.api.health import router as health_router
from app.api.market import router as market_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(market_router)
api_router.include_router(analysis_router)
api_router.include_router(backtest_router)


## Advanced analysis additions

- GET `/api/v1/analysis/multi-timeframe?symbol=BTCUSDT&intervals=15m,1h,4h&limit=200`
  fetches each timeframe concurrently and only returns an overall BUY/SELL when every requested timeframe independently produces the same directional signal. Any disagreement or NO TRADE result yields overall NO TRADE.
- GET `/api/v1/analysis/structure?symbol=BTCUSDT&interval=1h&limit=200`
  reports confirmed swing pivots, a basic BOS/CHOCH event, and the latest simple three-candle bullish/bearish fair-value gap.

SMC scope is deliberately a first-pass structural implementation, not a complete institutional order-flow model. Pivots require two candles on the right to confirm, so the newest two candles cannot create a confirmed pivot. BOS/CHOCH is evaluated against the latest confirmed swing and current last close. FVG detection is geometric and does not establish that a gap is valid, unmitigated, or tradeable. The endpoints use public Binance Spot OHLCV and remain research-only.
