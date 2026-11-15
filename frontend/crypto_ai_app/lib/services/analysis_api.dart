import 'dart:convert';

import 'package:http/http.dart' as http;

class AnalysisApi {
  AnalysisApi({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = (baseUrl ??
                const String.fromEnvironment(
                  'API_BASE_URL',
                  defaultValue: 'http://10.0.2.2:8000/api/v1',
                ))
            .replaceFirst(RegExp(r'/+$'), '');

  final http.Client _client;
  final String _baseUrl;

  Future<Map<String, dynamic>> fetchIntelligence({
    String symbol = 'BTCUSDT',
    String intervals = '15m,1h,4h',
  }) async {
    final uri = Uri.parse('$_baseUrl/analysis/intelligence').replace(
      queryParameters: {'symbol': symbol, 'intervals': intervals},
    );
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('API error ${response.statusCode}: ${_errorMessage(response.body)}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid analysis response format.');
    }
    return decoded;
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
