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


  Future<List<Map<String, dynamic>>> fetchCandles({
    String symbol = 'BTCUSDT',
    String interval = '15m',
    int limit = 80,
  }) async {
    final uri = _endpoint('market/candles', {
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

  Future<List<Map<String, dynamic>>> fetchSignals({String status = 'all', int limit = 50}) async {
    final uri = _endpoint('signals', {'status': status, 'limit': limit.toString()});
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
