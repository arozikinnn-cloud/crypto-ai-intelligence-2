from datetime import datetime, timezone
from app.services.market_data.base import MarketDataError


def normalize_liquidation_message(message: dict) -> dict:
    try:
        order = message["o"]
        side = str(order["S"]).upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("Invalid liquidation side.")
        quantity = float(order["q"])
        price = float(order["ap"] or order["p"])
        event_time = int(message["E"])
        if quantity <= 0 or price <= 0:
            raise ValueError("Invalid liquidation size or price.")
        return {
            "symbol": str(order["s"]).upper(),
            "side": side,
            "price": price,
            "quantity": quantity,
            "notional": price * quantity,
            "timestamp": datetime.fromtimestamp(event_time / 1000, tz=timezone.utc),
            "order_status": str(order["X"]),
            "note": (
                "BUY adalah likuidasi posisi short; SELL adalah likuidasi posisi long "
                "pada stream force-order Binance Futures."
            ),
        }
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise MarketDataError("Malformed Binance liquidation event.") from exc
