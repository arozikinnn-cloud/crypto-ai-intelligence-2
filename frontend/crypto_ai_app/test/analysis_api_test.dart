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
      expect(result['agent_status'], 'UNAVAILABLE');
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
      expect(result['agent_status'], 'UNAVAILABLE');
      expect(result['execution_ready'], isFalse);
      expect((result['context_notes'] as List).join(' '), contains('HTTP 500'));
    } finally {
      api.close();
    }
  });

  test('Android never enqueues TradingAgents jobs or sends server-only secrets', () async {
    var postCount = 0;
    final client = MockClient((request) async {
      if (request.method == 'POST') postCount++;
      if (request.method == 'GET' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response('Unauthorized', 401);
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
      expect(result['agent_status'], 'UNAVAILABLE');
      expect(result['execution_ready'], isFalse);
      expect(result['trade_plan'], isNull);
      expect((result['context_notes'] as List).join(' '), contains('HTTP 401'));
      expect(postCount, 0);
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
              'market_context': {
                'provider': 'bitget_usdt_futures',
                'collected_at': DateTime.now().toUtc().toIso8601String(),
              },
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



  test('returns a running TradingAgents job immediately without blocking the dashboard', () async {
    final client = MockClient((request) async {
      if (request.method == 'GET' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response(jsonEncode([
          {
            'id': 88,
            'symbol': 'BTCUSDT',
            'status': 'RUNNING',
            'created_at': '2026-11-20T00:00:00Z',
            'result': {},
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(
      client: client,
      baseUrl: 'https://example.test/api/v1',
    );

    try {
      final stopwatch = Stopwatch()..start();
      final result = await api.fetchTradingAgentsAnalysis();
      stopwatch.stop();

      expect(result['agent_status'], 'RUNNING');
      expect(result['side'], 'NO TRADE');
      expect(stopwatch.elapsed, lessThan(const Duration(seconds: 2)));
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


  test('keeps the last fresh agent reports visible while a newer job is running', () async {
    final client = MockClient((request) async {
      if (request.method == 'GET' &&
          request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response(jsonEncode([
          {
            'id': 9,
            'symbol': 'BTCUSDT',
            'status': 'RUNNING',
            'created_at': DateTime.now().toUtc().toIso8601String(),
            'result': null,
          },
          {
            'id': 8,
            'symbol': 'BTCUSDT',
            'status': 'COMPLETED',
            'created_at': DateTime.now().toUtc().subtract(const Duration(minutes: 5)).toIso8601String(),
            'completed_at': DateTime.now().toUtc().subtract(const Duration(minutes: 4)).toIso8601String(),
            'result': {
              'side': 'SELL',
              'rating': 'Sell',
              'reports': {'market_report': 'Laporan market terakhir'},
              'market_context': {
                'collected_at': DateTime.now().toUtc().toIso8601String(),
              },
              'timeframe_analyses': {},
              'trade_plan': null,
            },
          },
        ]), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final result = await api.fetchTradingAgentsAnalysis();
      expect(result['agent_status'], 'COMPLETED');
      expect(result['refresh_status'], 'RUNNING');
      expect(result['side'], 'SELL');
      expect((result['agent_reports'] as Map)['market_report'], 'Laporan market terakhir');
      expect((result['context_notes'] as List).join(' '), contains('sedang berjalan'));
    } finally {
      api.close();
    }
  });

  test('requests only V8 notifications and keeps the source signal id', () async {
    final client = MockClient((request) async {
      expect(request.url.queryParameters['strategy_mode'], 'TRADINGAGENTS_MULTI_AGENT_V8');
      return http.Response(jsonEncode([
        {
          'id': 12,
          'signal_id': 4,
          'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8',
          'symbol': 'BTCUSDT',
          'side': 'SELL',
          'entry': 61771.6,
          'stop_loss': 62109.98,
          'take_profit': 61264.03,
          'read': false,
        }
      ]), 200, headers: {'content-type': 'application/json'});
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final rows = await api.fetchNotifications(
        strategyMode: 'TRADINGAGENTS_MULTI_AGENT_V8',
      );
      expect(rows, hasLength(1));
      expect(rows.single['signal_id'], 4);
      expect(rows.single['side'], 'SELL');
      expect(rows.single['entry'], 61771.6);
    } finally {
      api.close();
    }
  });


  test('keeps a backend-active V8 signal active regardless of age', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/signals')) {
        return http.Response(jsonEncode([
          {
            'id': 1,
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'status': 'ACTIVE',
            'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8',
            'created_at': '2026-11-20T01:09:02Z',
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final rows = await api.fetchSignals(
        status: 'ACTIVE',
        strategyMode: 'TRADINGAGENTS_MULTI_AGENT_V8',
      );
      expect(rows.single['status'], 'ACTIVE');
    } finally {
      api.close();
    }
  });

  test('uses the same active signal levels in AI plan and Signal Center', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response(jsonEncode([
          {
            'id': 20,
            'symbol': 'BTCUSDT',
            'status': 'COMPLETED',
            'completed_at': DateTime.now().toUtc().toIso8601String(),
            'result': {
              'side': 'SELL',
              'trade_plan': {
                'entry': 61786.2,
                'stop_loss': 62143.96,
                'take_profit': 61249.56,
                'risk_reward': 1.5,
              },
              'market_context': {
                'collected_at': DateTime.now().toUtc().toIso8601String(),
              },
              'reports': {'market_report': 'Latest research'},
            },
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.path.endsWith('/signals')) {
        return http.Response(jsonEncode([
          {
            'id': 3,
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'status': 'ACTIVE',
            'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8',
            'created_at': DateTime.now().toUtc().toIso8601String(),
            'entry': 62119.8,
            'stop_loss': 62507.7,
            'take_profit': 61537.95,
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final result = await api.fetchTradingAgentsAnalysis();
      final plan = result['trade_plan'] as Map;
      final candidate = result['candidate_trade_plan'] as Map;
      expect(result['side'], 'SELL');
      expect(result['signal_alignment'], 'ALIGNED');
      expect((result['linked_signal'] as Map)['id'], 3);
      expect(plan['entry'], 62119.8);
      expect(plan['stop_loss'], 62507.7);
      expect(plan['take_profit'], 61537.95);
      expect(candidate['entry'], 61786.2);
    } finally {
      api.close();
    }
  });

  test('blocks a new AI direction that conflicts with an active signal', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/agent-analysis/jobs')) {
        return http.Response(jsonEncode([
          {
            'id': 21,
            'symbol': 'BTCUSDT',
            'status': 'COMPLETED',
            'completed_at': DateTime.now().toUtc().toIso8601String(),
            'result': {
              'side': 'BUY',
              'trade_plan': {'entry': 100, 'stop_loss': 98, 'take_profit': 103},
              'market_context': {
                'collected_at': DateTime.now().toUtc().toIso8601String(),
              },
              'reports': {'market_report': 'Latest research'},
            },
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      if (request.url.path.endsWith('/signals')) {
        return http.Response(jsonEncode([
          {
            'id': 4,
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'status': 'ACTIVE',
            'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8',
            'created_at': DateTime.now().toUtc().toIso8601String(),
            'entry': 100,
            'stop_loss': 102,
            'take_profit': 97,
          }
        ]), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response('Not found', 404);
    });
    final api = AnalysisApi(client: client, baseUrl: 'https://example.test/api/v1');
    try {
      final result = await api.fetchTradingAgentsAnalysis();
      expect(result['side'], 'NO TRADE');
      expect(result['ai_research_side'], 'BUY');
      expect(result['signal_alignment'], 'CONFLICT');
      expect(result['trade_plan'], isNull);
      expect((result['linked_signal'] as Map)['side'], 'SELL');
      expect((result['context_notes'] as List).join(' '), contains('Konflik arah'));
    } finally {
      api.close();
    }
  });

}
