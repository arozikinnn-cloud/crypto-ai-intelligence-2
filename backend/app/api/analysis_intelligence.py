import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.signals import record_signal
from app.schemas.analysis import AnalysisResponse
from app.schemas.intelligence import IntelligenceResponse
from app.schemas.order_flow import (
    AggTradesOrderFlowResponse,
    DerivativesContextResponse,
    OrderFlowResponse,
)
from app.schemas.structure import StructureResponse
from app.services.analysis.engine import analyze_market
from app.services.analysis.intelligence import build_intelligence_decision
from app.services.analysis.order_flow import analyze_order_flow
from app.services.analysis.order_book import analyze_order_book
from app.services.analysis.market_context import summarize_cvd_history, summarize_liquidations
from app.services.analysis.structure import analyze_structure
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.binance_aggtrades import BinanceAggTradesMarketData
from app.services.market_data.binance_futures import BinanceFuturesMarketData
from app.services.market_data.binance_order_book import BinanceOrderBookMarketData
from app.services.market_data.cvd_storage import read_cvd_history
from app.services.market_data.liquidation_storage import read_liquidation_history

router = APIRouter(prefix="/analysis", tags=["combined intelligence"])


async def _fetch_aggtrades_or_unavailable(client, symbol: str) -> dict:
    try:
        return await client.fetch_order_flow(symbol, 500)
    except MarketDataError:
        return {
            "symbol": symbol.upper(),
            "source_market": "binance_spot_aggtrades",
            "trade_count": 0,
            "buy_aggressor_volume": 0.0,
            "sell_aggressor_volume": 0.0,
            "net_delta": 0.0,
            "delta_percent": 0.0,
            "cumulative_delta": 0.0,
            "cvd_bucket_interval": "1m",
            "cvd_scope": "unavailable",
            "cvd_points": [],
            "bias": "UNAVAILABLE",
            "first_trade_time": None,
            "last_trade_time": None,
            "method_note": (
                "Data aggTrades tidak tersedia dari sumber Binance. "
                "Konfirmasi transaksi tidak terpenuhi; sistem akan memilih NO TRADE."
            ),
        }


async def _fetch_derivatives_or_unavailable(client, symbol: str, period: str) -> dict:
    try:
        return await client.fetch_derivatives_context(symbol, period)
    except MarketDataError:
        return {
            "symbol": symbol.upper(),
            "source_market": "unavailable",
            "open_interest_unit": "unknown",
            "open_interest": 0.0,
            "open_interest_change_percent": None,
            "open_interest_period": period,
            "funding_rate": 0.0,
            "funding_time": 0,
            "interpretation": (
                "Data open interest/funding tidak tersedia dari penyedia derivatif. "
                "Nilai nol di sini adalah placeholder, bukan pembacaan pasar."
            ),
        }


async def _fetch_order_book_or_unavailable(symbol: str) -> dict:
    try:
        snapshot = await BinanceOrderBookMarketData().fetch_order_book(symbol, 100)
        return {"available": True, **analyze_order_book(snapshot, depth_levels=20)}
    except (MarketDataError, ValueError):
        return {
            "available": False,
            "bias": "UNAVAILABLE",
            "note": (
                "Snapshot order book tidak tersedia; sistem tidak mengarang "
                "imbalance dan tidak menganggapnya sebagai absorption."
            ),
        }


@router.get("/intelligence", response_model=IntelligenceResponse)
async def combined_intelligence(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    intervals: str = Query(default="4h,1h,15m"),
    limit: int = Query(default=200, ge=60, le=500),
    order_flow_interval: str = Query(default="5m"),
    derivatives_period: str = Query(default="5m"),
    db: Session = Depends(get_db),
) -> IntelligenceResponse:
    selected = [item.strip() for item in intervals.split(",") if item.strip()]
    if not selected or len(selected) > 4 or len(set(selected)) != len(selected):
        raise HTTPException(
            status_code=422,
            detail="Provide 1–4 unique comma-separated intervals.",
        )
    if any(item not in BinanceMarketData.ALLOWED_INTERVALS for item in selected):
        raise HTTPException(status_code=422, detail="One or more intervals are unsupported.")
    if order_flow_interval not in BinanceMarketData.ALLOWED_INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported order-flow interval.")

    market = BinanceMarketData()
    futures = BinanceFuturesMarketData()
    aggtrades = BinanceAggTradesMarketData()
    try:
        tasks = [
            *(
                market.fetch_klines(symbol, interval, limit, closed_only=True)
                for interval in selected
            ),
            market.fetch_klines(
                symbol, order_flow_interval, min(limit, 100), closed_only=True
            ),
            _fetch_derivatives_or_unavailable(futures, symbol, derivatives_period),
            _fetch_aggtrades_or_unavailable(aggtrades, symbol),
            _fetch_order_book_or_unavailable(symbol),
        ]
        results = await asyncio.gather(*tasks)
        candle_sets = results[:len(selected)]
        flow_candles = results[len(selected)]
        derivatives_data = results[len(selected) + 1]
        aggtrades_data = results[len(selected) + 2]
        order_book_data = results[len(selected) + 3]
        analyses = [analyze_market(items) for items in candle_sets]
        structure_index = selected.index("1h") if "1h" in selected else 0
        structure_data = analyze_structure(candle_sets[structure_index])
        flow_data = analyze_order_flow(
            flow_candles, lookback=min(100, len(flow_candles))
        )
        cvd_history = summarize_cvd_history(read_cvd_history(db, symbol, limit=60))
        liquidation_context = summarize_liquidations(
            read_liquidation_history(db, symbol, hours=24)
        )
        market_context = {
            "cvd_history": cvd_history,
            "order_book": order_book_data,
            "liquidations": liquidation_context,
        }
        decision = build_intelligence_decision(
            [item["side"] for item in analyses],
            structure_data,
            flow_data,
            derivatives_data,
            aggtrades_data,
            market_context,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    timestamp = datetime.now(timezone.utc)
    record_signal(
        db,
        symbol,
        decision["side"],
        selected,
        decision["reasons"],
        str(getattr(candle_sets[0][-1], "close_time", candle_sets[0][-1])),
    )
    structure_response = StructureResponse(
        symbol=symbol.upper(),
        timeframe="1h" if "1h" in selected else selected[0],
        timestamp=timestamp,
        **structure_data,
    )
    return IntelligenceResponse(
        symbol=symbol.upper(),
        timestamp=timestamp,
        timeframe_analyses=[AnalysisResponse(**item) for item in analyses],
        structure=structure_response,
        order_flow=OrderFlowResponse(**flow_data),
        aggtrades_order_flow=AggTradesOrderFlowResponse(**aggtrades_data),
        derivatives=DerivativesContextResponse(**derivatives_data),
        market_context=market_context,
        **decision,
    )
