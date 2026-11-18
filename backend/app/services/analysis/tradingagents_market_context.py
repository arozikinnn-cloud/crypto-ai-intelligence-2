import asyncio
from datetime import datetime, timezone

from app.services.analysis.engine import analyze_market
from app.services.market_data.bitget import BitgetUsdtFuturesMarketData


TIMEFRAMES = ("5m", "15m", "30m", "1h")


def _order_book_summary(order_book: dict) -> dict:
    bid_notional = sum(price * quantity for price, quantity in order_book["bids"])
    ask_notional = sum(price * quantity for price, quantity in order_book["asks"])
    total = bid_notional + ask_notional
    return {
        "bid_notional": bid_notional,
        "ask_notional": ask_notional,
        "imbalance": (bid_notional - ask_notional) / total if total else 0.0,
        "bias": (
            "BID DOMINANT" if bid_notional > ask_notional
            else "ASK DOMINANT" if ask_notional > bid_notional
            else "BALANCED"
        ),
        "note": "Snapshot Bitget Futures; not historical order-flow data.",
        "best_bid": order_book["bids"][0][0],
        "best_ask": order_book["asks"][0][0],
        "timestamp": order_book["timestamp"],
    }


async def collect_bitget_v8_context(
    symbol: str, provider: BitgetUsdtFuturesMarketData | None = None
) -> dict:
    """Collect closed Bitget Futures candles and public derivatives context."""
    market = provider or BitgetUsdtFuturesMarketData()
    normalized = symbol.upper().strip()
    candle_sets = await asyncio.gather(*(
        market.fetch_klines(normalized, timeframe, 120, closed_only=True)
        for timeframe in TIMEFRAMES
    ))
    derivatives, order_book = await asyncio.gather(
        market.fetch_derivatives_context(normalized),
        market.fetch_order_book(normalized, 100),
    )

    analyses = {}
    for timeframe, candles in zip(TIMEFRAMES, candle_sets):
        if len(candles) < 80:
            raise ValueError(
                f"Bitget {timeframe} data is insufficient: {len(candles)} closed candles; "
                "at least 80 are required."
            )
        age_seconds = (
            datetime.now(timezone.utc) - candles[-1].close_time
        ).total_seconds()
        max_age = 2 * (candles[-1].close_time - candles[-2].close_time).total_seconds()
        if age_seconds > max_age:
            raise ValueError(f"Bitget {timeframe} candles are stale.")
        analysis = analyze_market(candles, risk_reward=1.5, atr_multiplier=1.5)
        analyses[timeframe] = {
            "side": analysis["side"],
            "entry": analysis["entry"],
            "stop_loss": analysis["stop_loss"],
            "take_profit": analysis["take_profit"],
            "risk_reward": analysis["risk_reward"],
            "confluence_score": analysis["confluence_score"],
            "reasons": analysis["reasons"],
            "indicators": analysis["indicators"],
            "candle_close_time": candles[-1].close_time.isoformat(),
            "candle_count": len(candles),
        }

    book = _order_book_summary(order_book)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    oi_timestamp = int(derivatives.get("open_interest_timestamp") or 0)
    book_timestamp = int(book.get("timestamp") or 0)
    if oi_timestamp <= 0 or now_ms - oi_timestamp > 10 * 60 * 1000:
        raise ValueError("Bitget open-interest snapshot is missing or stale.")
    if book_timestamp <= 0 or now_ms - book_timestamp > 2 * 60 * 1000:
        raise ValueError("Bitget order-book snapshot is missing or stale.")
    latest = analyses["15m"]
    context_text = [
        "VERIFIED EXCHANGE DATA — BITGET USDT-M FUTURES (public endpoints).",
        f"Symbol: {normalized}. All candles below are closed candles; UTC timestamps.",
        "Treat this Bitget Futures snapshot as authoritative for exact crypto prices. "
        "If Yahoo Finance or another research tool disagrees, report the discrepancy "
        "and do not replace Bitget prices with the other source.",
    ]
    for timeframe in TIMEFRAMES:
        item = analyses[timeframe]
        ind = item["indicators"]
        context_text.append(
            f"{timeframe}: side={item['side']}; close={ind['last_price']}; "
            f"MA40={ind['ma40']}; RSI16={ind['rsi16']}; ATR14={ind['atr14']}; "
            f"Tenkan={ind['ichimoku_tenkan']}; Kijun={ind['ichimoku_kijun']}; "
            f"KumoTop={ind['ichimoku_cloud_top']}; KumoBottom={ind['ichimoku_cloud_bottom']}; "
            f"reasons={' | '.join(item['reasons'])}"
        )
    context_text.append(
        f"Derivatives: open interest={derivatives['open_interest']} "
        f"{derivatives['open_interest_unit']}; funding rate={derivatives['funding_rate']}."
    )
    context_text.append(
        f"Order-book snapshot: best bid={book['best_bid']}; best ask={book['best_ask']}; "
        f"bid notional={book['bid_notional']}; ask notional={book['ask_notional']}; "
        f"imbalance={book['imbalance']} (positive means bid-side notional is larger)."
    )
    context_text.append(
        "Risk-plan reference only: 15m ATR-based stop and 1:1.5 target; "
        f"15m candidate side={latest['side']}, entry={latest['entry']}, "
        f"SL={latest['stop_loss']}, TP={latest['take_profit']}. "
        "These are not exchange orders and must pass multi-agent agreement and paper validation."
    )
    return {
        "provider": "bitget_usdt_futures",
        "symbol": normalized,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": analyses,
        "derivatives": derivatives,
        "order_book": book,
        "context_text": "\n".join(context_text),
    }


def finalize_v8_decision(
    rating: str, final_decision: str, reports: dict, market_context: dict
) -> dict:
    """Require TradingAgents and closed-candle multi-timeframe confirmation."""
    from app.services.analysis.tradingagents_result import normalize_tradingagents_result

    result = normalize_tradingagents_result(rating, final_decision, reports)
    agent_side = result["side"]
    timeframes = market_context["timeframes"]
    higher_timeframes = [timeframes[name]["side"] for name in ("1h", "30m", "15m")]
    five_minute_side = timeframes["5m"]["side"]
    confirmed = (
        agent_side in {"BUY", "SELL"}
        and all(side == agent_side for side in higher_timeframes)
        and five_minute_side in {agent_side, "NO TRADE"}
    )

    plan = None
    reasons = [
        f"TradingAgents rating: {result['rating']} ({agent_side}).",
        "Validasi data harga menggunakan Bitget USDT-M Futures.",
    ]
    for timeframe in ("1h", "30m", "15m", "5m"):
        item = timeframes[timeframe]
        reasons.append(f"{timeframe}: {item['side']} — " + "; ".join(item["reasons"]))
    if confirmed:
        candidate = timeframes["15m"]
        entry = float(candidate["entry"])
        stop = float(candidate["stop_loss"])
        target = float(candidate["take_profit"])
        risk = abs(entry - stop)
        reward = abs(target - entry)
        ratio = reward / risk if risk else 0.0
        valid = (
            entry > 0 and risk > 0
            and (stop < entry < target if agent_side == "BUY" else target < entry < stop)
            and 1.49 <= ratio <= 1.51
        )
        if valid:
            plan = {
                "symbol": market_context["symbol"],
                "side": agent_side,
                "entry": entry,
                "stop_loss": stop,
                "take_profit": target,
                "risk_reward": 1.5,
                "source": "Bitget closed 15m candles; ATR(14) x 1.5",
                "status": "PAPER_VALIDATION_REQUIRED",
            }
            reasons.append("TradingAgents dan 1H/30m/15m searah; rencana risiko 1:1.5 valid.")
        else:
            confirmed = False
            reasons.append("Rencana risiko gagal validasi harga atau rasio 1:1.5.")
    if not confirmed:
        result["side"] = "NO TRADE"
        reasons.append(
            "Tidak ada sinyal eksekusi: rating TradingAgents dan konfirmasi multi-timeframe "
            "belum sepakat atau data entry tidak valid."
        )

    result.update({
        "side": result["side"],
        "reasons": reasons,
        "market_context": market_context,
        "timeframe_analyses": timeframes,
        "trade_plan": plan if confirmed else None,
        "execution_ready": False,
        "paper_validation_required": plan is not None,
    })
    return result
