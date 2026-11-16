from types import SimpleNamespace

from worker import configured_collectors
from app.services.market_data.cvd_collector import stream_binance_aggtrades
from app.services.market_data.liquidation_collector import stream_binance_liquidations


def test_configured_collectors_builds_enabled_symbol_streams():
    settings = SimpleNamespace(
        cvd_collector_enabled=True,
        cvd_collector_symbol_list=["BTCUSDT", "ETHUSDT"],
        cvd_collector_flush_interval_seconds=2.0,
        liquidation_collector_enabled=True,
        liquidation_collector_symbol_list=["BTCUSDT"],
        liquidation_collector_flush_interval_seconds=3.0,
    )

    jobs = configured_collectors(settings)

    assert [(name, symbol) for name, _, symbol, _ in jobs] == [
        ("cvd-BTCUSDT", "BTCUSDT"),
        ("cvd-ETHUSDT", "ETHUSDT"),
        ("liquidations-BTCUSDT", "BTCUSDT"),
    ]
    assert jobs[0][1] is stream_binance_aggtrades
    assert jobs[0][3] == 2.0
    assert jobs[2][1] is stream_binance_liquidations
    assert jobs[2][3] == 3.0


def test_configured_collectors_respects_disabled_flags():
    settings = SimpleNamespace(
        cvd_collector_enabled=False,
        cvd_collector_symbol_list=["BTCUSDT"],
        cvd_collector_flush_interval_seconds=2.0,
        liquidation_collector_enabled=False,
        liquidation_collector_symbol_list=["BTCUSDT"],
        liquidation_collector_flush_interval_seconds=2.0,
    )

    assert configured_collectors(settings) == []
