import 'dart:convert';

import 'package:http/http.dart' as http;

class AnalysisApi {
  AnalysisApi({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = (baseUrl ??
                const String.fromEnvironment(
                  'API_BASE_URL',
                  defaultValue: 'https://crypto-ai-intelligence-2-backend.vercel.app/api/v1',
                ))
            .replaceFirst(RegExp(r'/+$'), '');

  final http.Client _client;
  final String _baseUrl;

  Uri _endpoint(String path, [Map<String, String>? query]) {
    if (_baseUrl.isEmpty) {
      throw StateError(
        'Alamat Backend belum dikonfigurasi. Build APK dengan '
        '--dart-define=API_BASE_URL=https://alamat-server/api/v1. '
        'Untuk HP dan komputer di Wi-Fi yang sama, gunakan alamat IP '
        'LAN komputer, bukan 10.0.2.2.',
      );
    }
    final base = Uri.tryParse(_baseUrl);
    if (base == null || !base.hasScheme || base.host.isEmpty) {
      throw StateError('API_BASE_URL tidak valid: $_baseUrl');
    }
    return base.replace(
      path: '${base.path.replaceFirst(RegExp(r'/+$'), '')}/$path',
      queryParameters: query,
    );
  }

  Future<Map<String, dynamic>> fetchIntelligence({
    String symbol = 'BTCUSDT',
    String intervals = '1h,15m,5m',
  }) async {
    final uri = _endpoint('analysis/intelligence', {
      'symbol': symbol,
      'intervals': intervals,
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception(
        'API error ${response.statusCode}: ${_errorMessage(response.body)}',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid analysis response format.');
    }
    return decoded;
  }


  Future<Map<String, dynamic>> fetchTradingAgentsAnalysis({
    String symbol = 'BTCUSDT',
    bool forceNew = false,
  }) async {
    Map<String, dynamic>? job;
    if (!forceNew) {
      final latestUri = _endpoint('agent-analysis/jobs', {
        'symbol': symbol,
        'limit': '1',
      });
      final latestResponse = await _client
          .get(latestUri, headers: const {'Accept': 'application/json'})
          .timeout(const Duration(seconds: 20));
      if (latestResponse.statusCode == 200) {
        final decoded = jsonDecode(latestResponse.body);
        if (decoded is List && decoded.isNotEmpty &&
            decoded.first is Map<String, dynamic>) {
          job = decoded.first as Map<String, dynamic>;
          final status = job['status']?.toString();
          if (status == 'COMPLETED') return _agentJobToDashboard(job);
          if (status == 'FAILED') {
            throw Exception('TradingAgents job failed: ${job['error_message'] ?? 'unknown error'}');
          }
        }
      } else if (latestResponse.statusCode != 404) {
        throw Exception(
          'TradingAgents API error ${latestResponse.statusCode}: '
          '${_errorMessage(latestResponse.body)}',
        );
      }
    }

    final hasActiveJob = job != null &&
        {'PENDING', 'RUNNING'}.contains(job['status']?.toString());
    if (job == null ||
        (!hasActiveJob && (forceNew || job['status'] != 'COMPLETED'))) {
      final createUri = _endpoint('agent-analysis/jobs', {'symbol': symbol});
      final createResponse = await _client
          .post(createUri, headers: const {'Accept': 'application/json'})
          .timeout(const Duration(seconds: 20));
      if (createResponse.statusCode != 202) {
        throw Exception(
          'Unable to start TradingAgents analysis (${createResponse.statusCode}): '
          '${_errorMessage(createResponse.body)}',
        );
      }
      final decoded = jsonDecode(createResponse.body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Invalid TradingAgents job response.');
      }
      job = decoded;
    }

    final jobId = job['id'];
    if (jobId is! int) throw const FormatException('TradingAgents job ID is missing.');
    for (var attempt = 0; attempt < 18; attempt++) {
      await Future<void>.delayed(const Duration(seconds: 5));
      final statusUri = _endpoint('agent-analysis/jobs/$jobId');
      final statusResponse = await _client
          .get(statusUri, headers: const {'Accept': 'application/json'})
          .timeout(const Duration(seconds: 20));
      if (statusResponse.statusCode != 200) {
        throw Exception('TradingAgents status error: ${statusResponse.statusCode}');
      }
      final statusPayload = jsonDecode(statusResponse.body);
      if (statusPayload is! Map<String, dynamic>) {
        throw const FormatException('Invalid TradingAgents status response.');
      }
      job = statusPayload;
      if (job['status'] == 'COMPLETED') return _agentJobToDashboard(job);
      if (job['status'] == 'FAILED') {
        throw Exception('TradingAgents job failed: ${job['error_message'] ?? 'unknown error'}');
      }
    }
    return _agentJobToDashboard(job!, timedOut: true);
  }

  Map<String, dynamic> _agentJobToDashboard(
    Map<String, dynamic> job, {
    bool timedOut = false,
  }) {
    final result = job['result'] is Map<String, dynamic>
        ? job['result'] as Map<String, dynamic>
        : <String, dynamic>{};
    final status = job['status']?.toString() ?? 'PENDING';
    final side = result['side']?.toString() ?? 'NO TRADE';
    final reports = result['reports'] is Map<String, dynamic>
        ? result['reports'] as Map<String, dynamic>
        : <String, dynamic>{};
    final decision = result['decision_text']?.toString() ?? '';
    final rawReasons = result['reasons'];
    final reasons = rawReasons is List
        ? rawReasons.map((item) => item.toString()).toList()
        : decision.isNotEmpty
            ? <String>[decision]
            : <String>[
                timedOut
                    ? 'Analisis multi-agent masih berjalan di background. Muat ulang beberapa saat lagi.'
                    : 'Menunggu TradingAgents worker memproses analisis.',
              ];
    final marketContext = result['market_context'] is Map<String, dynamic>
        ? result['market_context'] as Map<String, dynamic>
        : <String, dynamic>{};
    final rawTimeframes = result['timeframe_analyses'];
    final timeframeRows = rawTimeframes is Map
        ? rawTimeframes.entries.map((entry) => <String, dynamic>{
            'timeframe': entry.key.toString(),
            if (entry.value is Map) ...(entry.value as Map).cast<String, dynamic>(),
          }).toList()
        : <dynamic>[];
    final tradePlan = result['trade_plan'] is Map<String, dynamic>
        ? result['trade_plan'] as Map<String, dynamic>
        : null;
    return {
      'symbol': job['symbol'] ?? 'BTCUSDT',
      'timestamp': job['completed_at'] ?? job['created_at'],
      'side': status == 'COMPLETED' ? side : 'NO TRADE',
      'confluence_score': tradePlan == null ? 0 : 3,
      'max_confluence': 3,
      'score_note': 'Konfirmasi TradingAgents + Bitget Futures 1H/30m/15m; bukan probabilitas win-rate.',
      'reasons': reasons,
      'context_notes': <String>[
        'Status job: $status',
        if (result['market_data_note'] != null)
          result['market_data_note'].toString(),
        if (result['paper_validation_required'] == true)
          'Rencana entry menunggu validasi Paper Trading; belum boleh dieksekusi live.',
        result['risk_note']?.toString() ??
            'TradingAgents bukan order exchange; validasi risiko dan simulasi tetap diperlukan.',
      ],
      'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8',
      'agent_rating': result['rating'],
      'agent_status': status,
      'agent_reports': reports,
      'execution_ready': false,
      'trade_plan': tradePlan,
      'timeframe_analyses': timeframeRows,
      'market_context': marketContext,
      'derivatives': marketContext['derivatives'] ?? <String, dynamic>{},
    };
  }

  Future<List<Map<String, dynamic>>> fetchCandles({
    String symbol = 'BTCUSDT',
    String interval = '15m',
    int limit = 80,
  }) async {
    final uri = _endpoint('market/bitget/candles', {
      'symbol': symbol,
      'interval': interval,
      'limit': limit.toString(),
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 25));
    if (response.statusCode != 200) {
      throw Exception('Candles API error ${response.statusCode}: ${_errorMessage(response.body)}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['candles'] is! List) {
      throw const FormatException('Invalid candle response format.');
    }
    return (decoded['candles'] as List)
        .whereType<Map<String, dynamic>>()
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> fetchBacktest({
    String symbol = 'BTCUSDT',
    String interval = '1h',
    int limit = 1000,
  }) async {
    final uri = _endpoint('analysis/backtest', {
      'symbol': symbol,
      'interval': interval,
      'limit': limit.toString(),
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 30));
    if (response.statusCode != 200) {
      throw Exception('Backtest API error ${response.statusCode}: ${_errorMessage(response.body)}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid backtest response format.');
    }
    return decoded;
  }

  Future<List<Map<String, dynamic>>> fetchSignals({
    String status = 'all',
    int limit = 50,
    String? strategyMode,
  }) async {
    final uri = _endpoint('signals', {
      'status': status,
      'limit': limit.toString(),
      if (strategyMode != null) 'strategy_mode': strategyMode,
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Signal API error ${response.statusCode}: ${_errorMessage(response.body)}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) throw const FormatException('Invalid signal response format.');
    return decoded.whereType<Map<String, dynamic>>().toList(growable: false);
  }

  Future<Map<String, dynamic>> fetchSignalPerformance() async {
    final uri = _endpoint('signals/performance');
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Signal performance API error: ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid signal performance response.');
    }
    return decoded;
  }

  Future<void> closeSignal(int signalId) async {
    final uri = _endpoint('signals/$signalId/close');
    final response = await _client
        .post(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Unable to close signal: ${response.statusCode}');
    }
  }

  Future<List<Map<String, dynamic>>> fetchNotifications({
    bool unreadOnly = false,
  }) async {
    final uri = _endpoint('signals/notifications', {
      'unread_only': unreadOnly.toString(),
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception(
        'Notification API error ${response.statusCode}: '
        '${_errorMessage(response.body)}',
      );
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw const FormatException('Invalid notification response format.');
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .toList(growable: false);
  }

  Future<void> markNotificationRead(int notificationId) async {
    final uri = _endpoint('signals/notifications/$notificationId/read');
    final response = await _client
        .post(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception(
        'Unable to mark notification read: ${response.statusCode}',
      );
    }
  }

  String _errorMessage(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] != null) {
        return decoded['detail'].toString();
      }
    } catch (_) {
      // Keep the fallback message for non-JSON responses.
    }
    return 'Unable to retrieve market analysis.';
  }

  void close() => _client.close();
}
