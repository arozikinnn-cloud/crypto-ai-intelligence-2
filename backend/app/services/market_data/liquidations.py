from datetime import datetime, timezone
from math import isfinite
from app.services.market_data.base import MarketDataError


def normalize_liquidation_message(message: dict) -> dict:
    try:
        order = message["o"]
        symbol = str(order["s"]).upper()
        if not symbol.isalnum() or not 5 <= len(symbol) <= 20:
            raise ValueError("Invalid liquidation symbol.")
        side = str(order["S"]).upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("Invalid liquidation side.")
        quantity = float(order["q"])
        price = float(order["ap"] or order["p"])
        event_time = int(message["E"])
        if (
            not isfinite(quantity)
            or not isfinite(price)
            or quantity <= 0
            or price <= 0
            or event_time <= 0
        ):
            raise ValueError("Invalid liquidation size, price, or event time.")
        return {
            "symbol": symbol,
            "source_market": "binance_usdm_futures_force_order",
            "side": side,
            "price": price,
            "quantity": quantity,
            "notional": price * quantity,
            "timestamp": datetime.fromtimestamp(event_time / 1000, tz=timezone.utc),
            "order_status": str(order["X"]),
            "event_key": f"{symbol}:{int(order.get('i', event_time))}:{int(order.get('T', event_time))}",
            "note": (
                "BUY adalah likuidasi posisi short; SELL adalah likuidasi posisi long "
                "pada stream force-order Binance USD-M Futures."
            ),
        }
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise MarketDataError("Malformed Binance liquidation event.") from exc
