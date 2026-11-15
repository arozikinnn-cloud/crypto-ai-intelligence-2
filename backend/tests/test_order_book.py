import pytest

from app.services.analysis.order_book import analyze_order_book


def test_order_book_detects_bid_depth_imbalance():
    result = analyze_order_book({
        "symbol": "BTCUSDT",
        "bids": [[100, 10], [99, 5]],
        "asks": [[101, 2], [102, 1]],
    })
    assert result["bias"] == "BUY_DEPTH"
    assert result["imbalance"] > 0
    assert result["spread_bps"] > 0


def test_order_book_detects_ask_depth_imbalance():
    result = analyze_order_book({
        "symbol": "BTCUSDT",
        "bids": [[100, 1]],
        "asks": [[101, 10]],
    })
    assert result["bias"] == "SELL_DEPTH"


def test_order_book_rejects_crossed_book_and_bad_levels():
    with pytest.raises(ValueError, match="crossed"):
        analyze_order_book({
            "symbol": "BTCUSDT", "bids": [[101, 1]], "asks": [[100, 1]]
        })
    with pytest.raises(ValueError, match="Invalid"):
        analyze_order_book({
            "symbol": "BTCUSDT", "bids": [[100, -1]], "asks": [[101, 1]]
        })
