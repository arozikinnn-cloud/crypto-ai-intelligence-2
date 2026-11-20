import 'dart:convert';

import 'package:crypto_ai_app/services/analysis_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('keeps V8 trial dashboard read-only when TradingAgents is disabled', () async {
    final client = MockClient((request) async {
      if (request.method == 'GET' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response('[]', 200);
      }
      if (request.method == 'POST' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response(
          jsonEncode({
            'detail': 'TradingAgents V8 is not enabled. Configure its worker first.',
          }),
          503,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(
      client: client,
      baseUrl: 'https://example.test/api/v1',
    );

    try {
      final result = await api.fetchTradingAgentsAnalysis();

      expect(result['side'], 'NO TRADE');
      expect(result['agent_status'], 'DISABLED');
      expect(result['execution_ready'], isFalse);
      expect(result['trade_plan'], isNull);
      expect(result['strategy_mode'], 'TRADINGAGENTS_MULTI_AGENT_V8');
      expect(
        (result['context_notes'] as List).join(' '),
        contains('Tidak menggunakan sinyal RSI/MA/Ichimoku lama'),
      );
    } finally {
      api.close();
    }
  });

  test('shows read-only NO TRADE when preview backend is unavailable', () async {
    final client = MockClient((request) async {
      return http.Response('Internal Server Error', 500);
    });
    final api = AnalysisApi(
      client: client,
      baseUrl: 'https://example.test/api/v1',
    );

    try {
      final result = await api.fetchTradingAgentsAnalysis();

      expect(result['side'], 'NO TRADE');
      expect(result['agent_status'], 'DISABLED');
      expect(result['execution_ready'], isFalse);
      expect((result['context_notes'] as List).join(' '), contains('HTTP 500'));
    } finally {
      api.close();
    }
  });

  test('keeps the Android client read-only when manual enqueue requires a server token', () async {
    final client = MockClient((request) async {
      if (request.method == 'POST' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        expect(request.headers.containsKey('X-TradingAgents-Enqueue-Token'), isFalse);
        return http.Response(
          jsonEncode({'detail': 'Unauthorized TradingAgents enqueue request.'}),
          401,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(
      client: client,
      baseUrl: 'https://example.test/api/v1',
    );

    try {
      final result = await api.fetchTradingAgentsAnalysis(forceNew: true);

      expect(result['side'], 'NO TRADE');
      expect(result['agent_status'], 'DISABLED');
      expect(result['execution_ready'], isFalse);
      expect(result['trade_plan'], isNull);
      expect((result['context_notes'] as List).join(' '), contains('Unauthorized'));
    } finally {
      api.close();
    }
  });
  test('filters legacy V7 signals even when an older API ignores strategy_mode', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/signals')) {
        return http.Response(jsonEncode([
          {'id': 1, 'strategy_mode': 'LEGACY_UNVERSIONED', 'side': 'BUY'},
          {'id': 2, 'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8', 'side': 'SELL'},
        ]), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final rows = await api.fetchSignals(
        status: 'all',
        strategyMode: 'TRADINGAGENTS_MULTI_AGENT_V8',
      );
      expect(rows, hasLength(1));
      expect(rows.single['id'], 2);
      expect(rows.single['side'], 'SELL');
    } finally {
      api.close();
    }
  });


  test('reads the latest completed V8 job without enqueueing another run', () async {
    var postCount = 0;
    final client = MockClient((request) async {
      if (request.method == 'GET' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response(jsonEncode([
          {
            'id': 7,
            'symbol': 'BTCUSDT',
            'status': 'COMPLETED',
            'created_at': '2026-11-20T00:00:00Z',
            'completed_at': '2026-11-20T00:02:00Z',
            'result': {
              'side': 'NO TRADE',
              'reasons': ['TradingAgents and multi-timeframe confirmation disagree.'],
              'market_context': {'provider': 'bitget_usdt_futures'},
              'timeframe_analyses': {},
              'trade_plan': null,
            },
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      if (request.method == 'POST') {
        postCount++;
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(
      client: client,
      baseUrl: 'https://example.test/api/v1',
    );

    try {
      final result = await api.fetchTradingAgentsAnalysis();

      expect(result['side'], 'NO TRADE');
      expect(result['agent_status'], 'COMPLETED');
      expect(result['strategy_mode'], 'TRADINGAGENTS_MULTI_AGENT_V8');
      expect(postCount, 0);
    } finally {
      api.close();
    }
  });


  test('loads dashboard market context and historical baseline from live API routes', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/analysis/order-flow/aggtrades')) {
        return http.Response(jsonEncode({
          'symbol': 'BTCUSDT',
          'trade_count': 20,
          'buy_aggressor_volume': 3.0,
          'sell_aggressor_volume': 2.0,
          'net_delta': 1.0,
          'bias': 'BUY_PRESSURE',
          'cvd_points': [],
        }), 200);
      }
      if (request.url.path.endsWith('/market/bitget/structure')) {
        return http.Response(jsonEncode({
          'symbol': 'BTCUSDT',
          'trend': 'bearish',
          'event': 'none',
          'liquidity_sweep': 'none',
          'last_swing_high': 64000,
          'last_swing_low': 61000,
        }), 200);
      }
      if (request.url.path.endsWith('/analysis/order-flow/cvd-history')) {
        return http.Response(jsonEncode({
          'symbol': 'BTCUSDT',
          'cvd_scope': 'persisted_observed_history',
          'points': [
            {'cumulative_delta': 1.0},
            {'cumulative_delta': 2.0},
          ],
        }), 200);
      }
      if (request.url.path.endsWith('/analysis/liquidations/history')) {
        return http.Response(jsonEncode({
          'symbol': 'BTCUSDT',
          'event_count': 0,
          'points': [],
          'note': 'No observed events',
        }), 200);
      }
      if (request.url.path.endsWith('/analysis/backtest')) {
        return http.Response(jsonEncode({
          'symbol': 'BTCUSDT',
          'timeframe': '1h',
          'candles': 299,
          'train': {'trades': 10},
          'out_of_sample': {'trades': 11, 'win_rate_pct': 36.36},
          'quality_checks': {'minimum_oos_trades_met': false},
        }), 200);
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final flow = await api.fetchAggTradesOrderFlow();
      final structure = await api.fetchMarketStructure();
      final cvd = await api.fetchCvdHistory();
      final liquidations = await api.fetchLiquidationHistory();
      final backtest = await api.fetchBacktest(limit: 300);

      expect(flow['bias'], 'BUY_PRESSURE');
      expect(structure['trend'], 'bearish');
      expect(cvd['cvd_scope'], 'persisted_observed_history');
      expect(liquidations['event_count'], 0);
      expect((backtest['out_of_sample'] as Map)['trades'], 11);
    } finally {
      api.close();
    }
  });

}
