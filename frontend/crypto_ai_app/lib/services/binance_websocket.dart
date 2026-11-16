import 'dart:async';
import 'dart:convert';
import 'dart:io';

class BinanceLiveSnapshot {
  const BinanceLiveSnapshot({
    required this.connected, this.connectionMessage = 'Disconnected',
    this.symbol = '', this.lastPrice, this.changePercent, this.quoteVolume,
    this.lastTradePrice, this.lastTradeQuantity, this.tradeSide,
    this.buyAggressorVolume = 0, this.sellAggressorVolume = 0,
    this.lastTradeAt, this.bidQuantity, this.askQuantity, this.candleClose,
    this.updatedAt,
  });
  final bool connected;
  final String connectionMessage;
  final String symbol;
  final double? lastPrice, changePercent, quoteVolume, lastTradePrice, lastTradeQuantity;
  final String? tradeSide;
  final double buyAggressorVolume, sellAggressorVolume;
  final DateTime? lastTradeAt, updatedAt;
  final double? bidQuantity, askQuantity, candleClose;

  double? get orderBookImbalance {
    final bid = bidQuantity, ask = askQuantity;
    if (bid == null || ask == null || bid + ask == 0) return null;
    return (bid - ask) / (bid + ask) * 100;
  }

  BinanceLiveSnapshot copyWith({
    bool? connected, String? connectionMessage, String? symbol,
    double? lastPrice, double? changePercent, double? quoteVolume,
    double? lastTradePrice, double? lastTradeQuantity, String? tradeSide,
    double? buyAggressorVolume, double? sellAggressorVolume,
    DateTime? lastTradeAt, double? bidQuantity, double? askQuantity,
    double? candleClose, DateTime? updatedAt,
  }) => BinanceLiveSnapshot(
    connected: connected ?? this.connected,
    connectionMessage: connectionMessage ?? this.connectionMessage,
    symbol: symbol ?? this.symbol, lastPrice: lastPrice ?? this.lastPrice,
    changePercent: changePercent ?? this.changePercent,
    quoteVolume: quoteVolume ?? this.quoteVolume,
    lastTradePrice: lastTradePrice ?? this.lastTradePrice,
    lastTradeQuantity: lastTradeQuantity ?? this.lastTradeQuantity,
    tradeSide: tradeSide ?? this.tradeSide,
    buyAggressorVolume: buyAggressorVolume ?? this.buyAggressorVolume,
    sellAggressorVolume: sellAggressorVolume ?? this.sellAggressorVolume,
    lastTradeAt: lastTradeAt ?? this.lastTradeAt,
    bidQuantity: bidQuantity ?? this.bidQuantity,
    askQuantity: askQuantity ?? this.askQuantity,
    candleClose: candleClose ?? this.candleClose,
    updatedAt: updatedAt ?? this.updatedAt,
  );
}

/// Public Binance market-data streams; no API key or paid subscription needed.
class BinanceWebSocketFeed {
  static const _hosts = ['data-stream.binance.vision', 'stream.binance.com'];
  static const _connectTimeout = Duration(seconds: 12);
  static const _firstMessageTimeout = Duration(seconds: 12);

  final StreamController<BinanceLiveSnapshot> _controller =
      StreamController<BinanceLiveSnapshot>.broadcast();
  WebSocket? _socket;
  Timer? _reconnectTimer, _firstMessageTimer;
  String? _symbol, _activeHost;
  int _generation = 0, _reconnectAttempts = 0, _preferredHostIndex = 0;
  bool _disposed = false;
  BinanceLiveSnapshot _snapshot = const BinanceLiveSnapshot(connected: false);

  Stream<BinanceLiveSnapshot> get stream => _controller.stream;
  BinanceLiveSnapshot get snapshot => _snapshot;

  Future<void> connect(String symbol) async {
    final normalized = symbol.toLowerCase().trim();
    if (_disposed || normalized.isEmpty) return;
    _generation++;
    _reconnectAttempts = 0;
    _reconnectTimer?.cancel();
    _firstMessageTimer?.cancel();
    await _closeSocket();
    _symbol = normalized;
    _snapshot = BinanceLiveSnapshot(
      connected: false,
      connectionMessage: 'Connecting to Binance public market stream...',
      symbol: normalized.toUpperCase(),
    );
    _emit();
    unawaited(_open(_generation));
  }

  Future<void> _open(int generation) async {
    final symbol = _symbol;
    if (_disposed || symbol == null || generation != _generation) return;
    final streams = [
      '${symbol}@ticker', '${symbol}@aggTrade',
      '${symbol}@depth20@100ms', '${symbol}@kline_1m',
    ].join('/');
    final errors = <String>[];

    for (var offset = 0; offset < _hosts.length; offset++) {
      final index = (_preferredHostIndex + offset) % _hosts.length;
      final host = _hosts[index];
      final uri = Uri.https(host, '/stream', {'streams': streams});
      try {
        final socket = await WebSocket.connect(
          uri.toString(), compression: CompressionOptions.compressionOff,
        ).timeout(_connectTimeout);
        if (_disposed || generation != _generation) {
          await socket.close();
          return;
        }
        _socket = socket;
        _activeHost = host;
        _preferredHostIndex = index;
        _reconnectAttempts = 0;
        socket.pingInterval = const Duration(seconds: 20);
        _snapshot = _snapshot.copyWith(
          connected: true,
          connectionMessage: 'Connected to $host • waiting for market data',
        );
        _emit();
        _firstMessageTimer?.cancel();
        _firstMessageTimer = Timer(_firstMessageTimeout, () {
          if (!_disposed && generation == _generation && _snapshot.updatedAt == null) {
            _scheduleReconnect(generation, 'Connected to $host but no market data arrived');
          }
        });
        socket.listen(
          (event) => _handleMessage(event, generation),
          onError: (Object error) => _scheduleReconnect(generation, 'WebSocket stream error: $error'),
          onDone: () => _scheduleReconnect(generation, 'Binance closed the connection'),
          cancelOnError: true,
        );
        return;
      } catch (error) {
        errors.add('$host: $error');
        if (_disposed || generation != _generation) return;
      }
    }
    _preferredHostIndex = (_preferredHostIndex + 1) % _hosts.length;
    _scheduleReconnect(generation, 'Unable to connect to Binance (${errors.join(' | ')})');
  }

  void _handleMessage(dynamic event, int generation) {
    if (_disposed || generation != _generation) return;
    _firstMessageTimer?.cancel();
    try {
      final decoded = jsonDecode(event as String);
      if (decoded is! Map) return;
      final data = decoded['data'];
      if (data is! Map) return;
      final type = data['e'];
      final now = DateTime.now().toUtc();
      var next = _snapshot;
      if (type == '24hrTicker') {
        next = next.copyWith(
          lastPrice: _number(data['c']), changePercent: _number(data['P']),
          quoteVolume: _number(data['q']), updatedAt: now,
        );
      } else if (type == 'aggTrade') {
        final quantity = _number(data['q']) ?? 0;
        final isSellAggressor = data['m'] == true;
        next = next.copyWith(
          lastTradePrice: _number(data['p']), lastTradeQuantity: quantity,
          tradeSide: isSellAggressor ? 'SELL' : 'BUY',
          buyAggressorVolume: next.buyAggressorVolume + (isSellAggressor ? 0 : quantity),
          sellAggressorVolume: next.sellAggressorVolume + (isSellAggressor ? quantity : 0),
          lastTradeAt: now, updatedAt: now,
        );
        final tradePrice = _number(data['p']);
        if (tradePrice != null) next = next.copyWith(lastPrice: tradePrice);
      } else if (type == 'depthUpdate') {
        next = next.copyWith(
          bidQuantity: _sumBook(data['b']), askQuantity: _sumBook(data['a']),
          updatedAt: now,
        );
      } else if (type == 'kline') {
        final candle = data['k'];
        if (candle is Map) {
          next = next.copyWith(candleClose: _number(candle['c']), updatedAt: now);
        }
      }
      if (next.updatedAt != null && next.updatedAt != _snapshot.updatedAt) {
        next = next.copyWith(connectionMessage: 'Live data active • ${_activeHost ?? 'Binance'}');
      }
      _snapshot = next;
      _emit();
    } catch (_) {
      // Ignore malformed or unexpected public stream messages.
    }
  }

  double? _number(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '');
  }

  double? _sumBook(dynamic levels) {
    if (levels is! List) return null;
    var total = 0.0;
    for (final level in levels) {
      if (level is List && level.length > 1) total += _number(level[1]) ?? 0;
    }
    return total;
  }

  void _scheduleReconnect(int generation, [String reason = 'Connection interrupted']) {
    if (_disposed || generation != _generation || (_reconnectTimer?.isActive ?? false)) return;
    _firstMessageTimer?.cancel();
    unawaited(_closeSocket());
    _reconnectAttempts++;
    final exponent = (_reconnectAttempts - 1).clamp(0, 4);
    final delaySeconds = (3 * (1 << exponent)).clamp(3, 30).toInt();
    _snapshot = _snapshot.copyWith(
      connected: false, connectionMessage: '$reason • retry in ${delaySeconds}s',
    );
    _emit();
    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () {
      _reconnectTimer = null;
      unawaited(_open(generation));
    });
  }

  void _emit() {
    if (!_controller.isClosed) _controller.add(_snapshot);
  }

  Future<void> _closeSocket() async {
    final socket = _socket;
    _socket = null;
    _activeHost = null;
    if (socket != null) {
      try { await socket.close(WebSocketStatus.normalClosure); } catch (_) {}
    }
  }

  Future<void> disconnect() async {
    _generation++;
    _reconnectTimer?.cancel();
    _firstMessageTimer?.cancel();
    await _closeSocket();
    _snapshot = _snapshot.copyWith(
      connected: false, connectionMessage: 'Disconnected while app is inactive',
    );
    _emit();
  }

  Future<void> dispose() async {
    _disposed = true;
    _generation++;
    _reconnectTimer?.cancel();
    _firstMessageTimer?.cancel();
    await _closeSocket();
    await _controller.close();
  }
}
