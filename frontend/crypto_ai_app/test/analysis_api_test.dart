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
}
