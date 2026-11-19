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

}
