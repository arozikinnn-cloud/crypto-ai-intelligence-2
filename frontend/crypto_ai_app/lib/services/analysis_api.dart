import 'dart:convert';

import 'package:http/http.dart' as http;

class AnalysisApi {
  AnalysisApi({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = (baseUrl ??
                const String.fromEnvironment(
                  'API_BASE_URL',
                  defaultValue: 'https://crypto-ai-intelligence-2-backend-git-fe-0e1088-arozikinnn-cloud.vercel.app/api/v1',
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
    // The Android app is a public client: it must never enqueue expensive AI
    // jobs or carry the server-only enqueue token. GitHub Actions runs the
    // worker; the app only reads persisted jobs from Neon.
    final latestUri = _endpoint('agent-analysis/jobs', {
      'symbol': symbol,
      'limit': '5',
    });
    final latestResponse = await _client
        .get(latestUri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));

    if (latestResponse.statusCode == 401 ||
        latestResponse.statusCode == 403 ||
        latestResponse.statusCode == 404 ||
        latestResponse.statusCode >= 500) {
      return _agentUnavailableDashboard(
        symbol,
        'Backend V8 tidak dapat membaca histori analisis '
        '(HTTP ${latestResponse.statusCode}). Periksa deployment V8 dan akses API.',
      );
    }
    if (latestResponse.statusCode != 200) {
      return _agentUnavailableDashboard(
        symbol,
        'Backend V8 mengembalikan HTTP ${latestResponse.statusCode}.',
      );
    }

    final decoded = jsonDecode(latestResponse.body);
    if (decoded is! List) {
      return _agentUnavailableDashboard(
        symbol,
        'Format histori TradingAgents dari backend tidak valid.',
      );
    }
    final jobs = decoded
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
    if (jobs.isEmpty) {
      return await _attachActiveSignal(
        _agentUnavailableDashboard(
          symbol,
          'Belum ada hasil TradingAgents tersimpan. Worker terjadwal akan mengisi histori.',
        ),
        symbol,
      );
    }

    final latestJob = jobs.first;
    Map<String, dynamic>? freshCompleted;
    Map<String, dynamic>? runningJob;
    for (final job in jobs) {
      final status = job['status']?.toString();
      if (runningJob == null && (status == 'PENDING' || status == 'RUNNING')) {
        runningJob = job;
      }
      if (status == 'COMPLETED' && _isFreshAgentJob(job)) {
        freshCompleted = job;
        break;
      }
    }

    // Keep the last valid report visible while a newer scheduled analysis is
    // running. A transient PENDING/RUNNING job must not blank all agent cards.
    if (freshCompleted != null) {
      final dashboard = _agentJobToDashboard(freshCompleted);
      if (runningJob != null &&
          runningJob['id'] != freshCompleted['id']) {
        return await _attachActiveSignal({
          ...dashboard,
          'refresh_status': runningJob['status'],
          'context_notes': <String>[
            ...(dashboard['context_notes'] is List
                ? (dashboard['context_notes'] as List)
                    .map((item) => item.toString())
                : <String>[]),
            'Analisis TradingAgents terbaru sedang berjalan; laporan selesai terakhir tetap ditampilkan sampai hasil baru tersimpan.',
          ],
        }, symbol);
      }
      return await _attachActiveSignal(dashboard, symbol);
    }

    final latestStatus = latestJob['status']?.toString();
    if (latestStatus == 'COMPLETED') {
      return await _attachActiveSignal(_agentStaleDashboard(latestJob), symbol);
    }
    if (latestStatus == 'FAILED') {
      return await _attachActiveSignal(
        _agentUnavailableDashboard(
          symbol,
          'Analisis terakhir gagal: ${latestJob['error_message'] ?? 'unknown error'}',
        ),
        symbol,
      );
    }
    if (latestStatus == 'PENDING' || latestStatus == 'RUNNING') {
      // Do not hold the whole dashboard open while a cloud worker runs.
      return await _attachActiveSignal(
        _agentJobToDashboard(latestJob, timedOut: true),
        symbol,
      );
    }
    return await _attachActiveSignal(
      _agentUnavailableDashboard(
        symbol,
        'Belum ada hasil analisis TradingAgents yang dapat ditampilkan.',
      ),
      symbol,
    );
  }

  Future<Map<String, dynamic>> _attachActiveSignal(
    Map<String, dynamic> dashboard,
    String symbol,
  ) async {
    try {
      final activeSignals = await fetchSignals(
        status: 'ACTIVE',
        limit: 100,
        strategyMode: 'TRADINGAGENTS_MULTI_AGENT_V8',
      );
      Map<String, dynamic>? active;
      for (final signal in activeSignals) {
        if (signal['symbol']?.toString().toUpperCase() == symbol.toUpperCase()) {
          active = signal;
          break;
        }
      }
      if (active == null) return dashboard;

      final linked = Map<String, dynamic>.from(dashboard);
      linked['linked_signal'] = active;
      final aiSide = linked['side']?.toString().toUpperCase() ?? 'NO TRADE';
      final activeSide = active['side']?.toString().toUpperCase() ?? 'NO TRADE';
      final signalId = active['id']?.toString() ?? '?';
      final notes = linked['context_notes'] is List
          ? (linked['context_notes'] as List).map((item) => item.toString()).toList()
          : <String>[];

      if (aiSide == activeSide && (aiSide == 'BUY' || aiSide == 'SELL')) {
        final entry = _numberOrNull(active['entry']);
        final stop = _numberOrNull(active['stop_loss']);
        final target = _numberOrNull(active['take_profit']);
        if (entry != null && stop != null && target != null) {
          final risk = (entry - stop).abs();
          final reward = (target - entry).abs();
          final rr = risk > 0 ? reward / risk : null;
          linked['candidate_trade_plan'] = linked['trade_plan'];
          linked['trade_plan'] = <String, dynamic>{
            'symbol': active['symbol'] ?? symbol,
            'side': activeSide,
            'entry': entry,
            'stop_loss': stop,
            'take_profit': target,
            if (rr != null) 'risk_reward': rr,
            'status': 'ACTIVE_SIGNAL_TRACKED',
            'source': 'Signal Center active signal #$signalId',
          };
        }
        linked['signal_alignment'] = 'ALIGNED';
        notes.add(
          'AI dan Signal Center searah ($activeSide). Sinyal aktif #$signalId '
          'menjadi acuan level Entry/SL/TP sampai hasil TP/SL terkonfirmasi.',
        );
      } else if (aiSide == 'BUY' || aiSide == 'SELL') {
        linked['ai_research_side'] = aiSide;
        linked['side'] = 'NO TRADE';
        linked['trade_plan'] = null;
        linked['signal_alignment'] = 'CONFLICT';
        final conflict =
            'Konflik arah: AI terbaru $aiSide, tetapi sinyal aktif #$signalId adalah $activeSide. '
            'Sistem menahan sinyal baru sampai sinyal aktif selesai atau tervalidasi.';
        linked['reasons'] = <String>[
          if (linked['reasons'] is List)
            ...(linked['reasons'] as List).map((item) => item.toString()),
          conflict,
        ];
        linked['score_note'] = conflict;
        notes.add(conflict);
      } else {
        linked['signal_alignment'] = 'ACTIVE_SIGNAL_TRACKED';
        notes.add(
          'Sinyal aktif #$signalId ($activeSide) tetap dipantau di Signal Center; '
          'analisis AI terbaru belum memberikan sinyal baru.',
        );
      }
      linked['context_notes'] = notes;
      return linked;
    } catch (_) {
      // Signal linkage is supplemental; a notifications outage must not hide
      // the latest persisted TradingAgents report.
      return dashboard;
    }
  }

  double? _numberOrNull(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '');
  }

  bool _isFreshAgentJob(Map<String, dynamic> job) {
    final result = job['result'] is Map<String, dynamic>
        ? job['result'] as Map<String, dynamic>
        : <String, dynamic>{};
    final context = result['market_context'] is Map<String, dynamic>
        ? result['market_context'] as Map<String, dynamic>
        : <String, dynamic>{};
    final collectedAt = DateTime.tryParse(
          context['collected_at']?.toString() ?? '',
        ) ??
        DateTime.tryParse(job['completed_at']?.toString() ?? '');
    if (collectedAt == null) return false;
    final age = DateTime.now().toUtc().difference(collectedAt.toUtc());
    // The scheduled free-tier TradingAgents worker runs hourly. Keep the
    // result visible for a bounded 90-minute window, then fail closed to NO TRADE.
    return age >= const Duration(seconds: -60) &&
        age <= const Duration(minutes: 90);
  }

  Map<String, dynamic> _agentStaleDashboard(Map<String, dynamic> job) {
    final dashboard = _agentJobToDashboard(job);
    final result = job['result'] is Map<String, dynamic>
        ? job['result'] as Map<String, dynamic>
        : <String, dynamic>{};
    final context = result['market_context'] is Map<String, dynamic>
        ? result['market_context'] as Map<String, dynamic>
        : <String, dynamic>{};
    final collectedAt = context['collected_at']?.toString() ??
        job['completed_at']?.toString() ??
        'waktu tidak diketahui';
    return {
      ...dashboard,
      'side': 'NO TRADE',
      'agent_status': 'STALE',
      'confluence_score': 0,
      'score_note': 'Hasil TradingAgents melewati batas kesegaran 30 menit.',
      'reasons': <String>[
        'Hasil AI terakhir sudah kedaluwarsa; menunggu analisis baru.',
        'Data pasar AI terakhir dikumpulkan: $collectedAt.',
      ],
      'context_notes': <String>[
        'Status AI: STALE',
        'Rencana lama tidak ditampilkan sebagai sinyal aktif.',
        'Tidak ada order exchange yang dibuat.',
      ],
      'execution_ready': false,
      'trade_plan': null,
      'timeframe_analyses': <dynamic>[],
      'market_context': <String, dynamic>{},
      'derivatives': <String, dynamic>{},
    };
  }

  Map<String, dynamic> _agentUnavailableDashboard(
    String symbol,
    String detail,
  ) => {
    'symbol': symbol,
    'side': 'NO TRADE',
    'confluence_score': 0,
    'max_confluence': 3,
    'score_note': 'TradingAgents belum aktif; tidak ada sinyal trading yang diterbitkan.',
    'reasons': <String>[
      'Hasil TradingAgents belum tersedia. Periksa worker, kredensial model, dan akses backend.',
    ],
    'context_notes': <String>[
      'Status AI: UNAVAILABLE',
      'Tidak menggunakan sinyal RSI/MA/Ichimoku lama sebagai pengganti AI V8.',
      'Tidak ada order exchange yang dibuat.',
      if (detail.isNotEmpty) detail,
    ],
    'strategy_mode': 'TRADINGAGENTS_MULTI_AGENT_V8',
    'agent_status': 'UNAVAILABLE',
    'agent_reports': <String, dynamic>{},
    'execution_ready': false,
    'trade_plan': null,
    'timeframe_analyses': <dynamic>[],
    'market_context': <String, dynamic>{},
    'derivatives': <String, dynamic>{},
  };

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

  Future<Map<String, dynamic>> fetchAggTradesOrderFlow({String symbol = 'BTCUSDT'}) async {
    final uri = _endpoint('analysis/order-flow/aggtrades', {
      'symbol': symbol,
      'limit': '500',
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 25));
    if (response.statusCode != 200) {
      throw Exception('Order-flow API error ${response.statusCode}: ${_errorMessage(response.body)}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid order-flow response format.');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> fetchCvdHistory({String symbol = 'BTCUSDT', int limit = 60}) async {
    final uri = _endpoint('analysis/order-flow/cvd-history', {
      'symbol': symbol,
      'limit': limit.toString(),
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('CVD API error: ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid CVD response format.');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> fetchBitgetDerivatives({String symbol = 'BTCUSDT'}) async {
    final uri = _endpoint('market/bitget/derivatives', {'symbol': symbol});
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Bitget derivatives API error: ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid Bitget derivatives response format.');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> fetchBitgetOrderBook({
    String symbol = 'BTCUSDT',
    int limit = 100,
  }) async {
    final uri = _endpoint('market/bitget/order-book', {
      'symbol': symbol,
      'limit': limit.toString(),
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Bitget order-book API error: ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid Bitget order-book response format.');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> fetchMarketStructure({String symbol = 'BTCUSDT', String interval = '1h'}) async {
    final uri = _endpoint('market/bitget/structure', {
      'symbol': symbol,
      'interval': interval,
      'limit': '200',
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 25));
    if (response.statusCode != 200) {
      throw Exception('Market-structure API error: ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid market-structure response format.');
    }
    return decoded;
  }

  Future<Map<String, dynamic>> fetchLiquidationHistory({String symbol = 'BTCUSDT'}) async {
    final uri = _endpoint('analysis/liquidations/history', {
      'symbol': symbol,
      'hours': '24',
    });
    final response = await _client
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Liquidation API error: ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid liquidation response format.');
    }
    return decoded;
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
    final rows = decoded.whereType<Map<String, dynamic>>();
    // Enforce version isolation on the client as well as the API. This prevents
    // a stale/older backend that ignores strategy_mode from leaking V7 signals
    // into the V8 Signal Center.
    final filtered = strategyMode == null
        ? rows
        : rows.where((item) => item['strategy_mode']?.toString() == strategyMode);
    // An active signal does not become stale merely because it is older
    // than 30 minutes. The backend owns its TP/SL lifecycle; only a confirmed
    // outcome or explicit invalidation may change the persisted status.
    return filtered
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
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
    String? strategyMode,
  }) async {
    final uri = _endpoint('signals/notifications', {
      'unread_only': unreadOnly.toString(),
      if (strategyMode != null) 'strategy_mode': strategyMode,
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
