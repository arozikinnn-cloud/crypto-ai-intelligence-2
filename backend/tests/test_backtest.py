from datetime import datetime, timedelta, timezone
import pytest
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.backtest import run_strategy_backtest
from app.schemas.backtest import BacktestResponse


def make_series(count: int = 180) -> list[NormalizedCandle]:
    result = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        price = 100 + index * 0.1 + (5 if (index // 25) % 2 else 0)
        previous = 100 + max(index - 1, 0) * 0.1 + (5 if (max(index - 1, 0) // 25) % 2 else 0)
        result.append(
            NormalizedCandle(
                symbol="BTCUSDT", timeframe="1h",
                open_time=start + timedelta(hours=index),
                close_time=start + timedelta(hours=index, minutes=59),
                open=previous, high=max(previous, price) + 0.2,
                low=min(previous, price) - 0.2, close=price,
                volume=100, quote_volume=price * 100, trades=50,
            )
        )
    return result


def test_backtest_returns_train_and_out_of_sample_metrics():
    result = run_strategy_backtest(make_series())
    assert result["train"]["trades"] >= 0
    assert result["out_of_sample"]["trades"] >= 0
    assert result["fee_bps_per_side"] == 10.0
    assert result["slippage_bps_per_side"] == 5.0
    assert "RSI16" in result["strategy"]
    assert "MA40" in result["strategy"]
    assert "Ichimoku" in result["strategy"]
    assert "not a full H1/M15/M5" in result["warning"]
    assert "overall" in result
    parsed = BacktestResponse(**result)
    assert parsed.quality_checks == result["quality_checks"]
    assert parsed.out_of_sample.expectancy_pct == result["out_of_sample"]["expectancy_pct"]
    assert parsed.signal_count == result["signal_count"]


def test_backtest_rejects_too_little_history():
    with pytest.raises(ValueError):
        run_strategy_backtest(make_series(80))
