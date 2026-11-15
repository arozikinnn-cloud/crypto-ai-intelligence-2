from app.services.market_data.base import MarketDataError
from app.services.market_data.liquidations import normalize_liquidation_message
import pytest


def test_normalize_short_liquidation_event():
    event = normalize_liquidation_message({
        "E": 1760000000000,
        "o": {
            "s": "BTCUSDT", "S": "BUY", "q": "0.5",
            "ap": "60000", "p": "59900", "X": "FILLED",
        },
    })
    assert event["symbol"] == "BTCUSDT"
    assert event["source_market"] == "binance_usdm_futures_force_order"
    assert event["side"] == "BUY"
    assert event["notional"] == 30000


def test_reject_malformed_liquidation_event():
    with pytest.raises(MarketDataError):
        normalize_liquidation_message({"o": {}})


def test_reject_non_finite_liquidation_values():
    with pytest.raises(MarketDataError):
        normalize_liquidation_message({
            "E": 1760000000000,
            "o": {
                "s": "BTCUSDT", "S": "SELL", "q": "inf",
                "ap": "60000", "p": "60000", "X": "FILLED",
            },
        })
