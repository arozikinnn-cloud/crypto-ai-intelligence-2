import 'dart:async';
import 'dart:convert';
import 'dart:io';

class BinanceLiveSnapshot {
  const BinanceLiveSnapshot({
    required this.connected,
    this.symbol = '',
    this.lastPrice,
    this.changePercent,
    this.quoteVolume,
    this.lastTradePrice,
    this.lastTradeQuantity,
    this.tradeSide,
    this.buyAggressorVolume = 0,
    this.sellAggressorVolume = 0,
    this.lastTradeAt,
    this.bidQuantity,
    this.askQuantity,
    this.candleClose,
    this.updatedAt,
  });

  final bool connected;
  final String symbol;
  final double? lastPrice;
  final double? changePercent;
  final double? quoteVolume;
  final double? lastTradePrice;
  final double? lastTradeQuantity;
  final String? tradeSide;
  final double buyAggressorVolume;
  final double sellAggressorVolume;
  final DateTime? lastTradeAt;
  final double? bidQuantity;
  final double? askQuantity;
  final double? candleClose;
  final DateTime? updatedAt;

  double? get orderBookImbalance {
    final bid = bidQuantity;
    final ask = askQuantity;
    if (bid == null || ask == null || bid + ask == 0) return null;
    return (bid - ask) / (bid + ask) * 100;
  }

  BinanceLiveSnapshot copyWith({
    bool? connected,
    String? symbol,
    double? lastPrice,
    double? changePercent,
    double? quoteVolume,
    double? lastTradePrice,
    double? lastTradeQuantity,
    String? tradeSide,
    double? buyAggressorVolume,
    double? sellAggressorVolume,
    DateTime? lastTradeAt,
    double? bidQuantity,
    double? askQuantity,
    double? candleClose,
    DateTime? updatedAt,
  }) => BinanceLiveSnapshot(
    connected: connected ?? this.connected,
    symbol: symbol ?? this.symbol,
    lastPrice: lastPrice ?? this.lastPrice,
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

/// Public Binance Spot streams. No API key or paid subscription is required.
class BinanceWebSocketFeed {
  final StreamController<BinanceLiveSnapshot> _controller =
      StreamController<BinanceLiveSnapshot>.broadcast();

  WebSocket? _socket;
  Timer? _reconnectTimer;
  String? _symbol;
  int _generation = 0;
  bool _disposed = false;
  BinanceLiveSnapshot _snapshot =
      const BinanceLiveSnapshot(connected: false);

  Stream<BinanceLiveSnapshot> get stream => _controller.stream;
  BinanceLiveSnapshot get snapshot => _snapshot;

  Future<void> connect(String symbol) async {
    final normalized = symbol.toLowerCase();
    if (_disposed) return;
    _generation++;
    _reconnectTimer?.cancel();
    await _closeSocket();
    _symbol = normalized;
    _snapshot = BinanceLiveSnapshot(
      connected: false,
      symbol: normalized.toUpperCase(),
    );
    _emit();
    _open(_generation);
  }

  void _open(int generation) {
    final symbol = _symbol;
    if (_disposed || symbol == null || generation != _generation) return;
    final streams = [
      '${symbol}@ticker',
      '${symbol}@aggTrade',
      '${symbol}@depth20@100ms',
      '${symbol}@kline_1m',
    ].join('/');
    final uri = Uri.parse(
      'wss://stream.binance.com:9443/stream?streams=$streams',
    );
    WebSocket.connect(uri.toString(), compression: CompressionOptions.compressionOff)
        .then((socket) async {
      if (_disposed || generation != _generation) {
        await socket.close();
        return;
      }
      _socket = socket;
      _snapshot = _snapshot.copyWith(connected: true);
      _emit();
      socket.listen(
        (event) => _handleMessage(event, generation),
        onError: (_) => _scheduleReconnect(generation),
        onDone: () => _scheduleReconnect(generation),
        cancelOnError: true,
      );
    }).catchError((_) {
      _scheduleReconnect(generation);
    });
  }

  void _handleMessage(dynamic event, int generation) {
    if (_disposed || generation != _generation) return;
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
          lastPrice: _number(data['c']),
          changePercent: _number(data['P']),
          quoteVolume: _number(data['q']),
          updatedAt: now,
        );
      } else if (type == 'aggTrade') {
        final quantity = _number(data['q']) ?? 0;
        final isSellAggressor = data['m'] == true;
        next = next.copyWith(
          lastTradePrice: _number(data['p']),
          lastTradeQuantity: quantity,
          tradeSide: isSellAggressor ? 'SELL' : 'BUY',
          buyAggressorVolume: next.buyAggressorVolume + (isSellAggressor ? 0 : quantity),
          sellAggressorVolume: next.sellAggressorVolume + (isSellAggressor ? quantity : 0),
          lastTradeAt: now,
          updatedAt: now,
        );
        final tradePrice = _number(data['p']);
        if (tradePrice != null) next = next.copyWith(lastPrice: tradePrice);
      } else if (type == 'depthUpdate') {
        next = next.copyWith(
          bidQuantity: _sumBook(data['b']),
          askQuantity: _sumBook(data['a']),
          updatedAt: now,
        );
      } else if (type == 'kline') {
        final candle = data['k'];
        if (candle is Map) {
          next = next.copyWith(
            candleClose: _number(candle['c']),
            updatedAt: now,
          );
        }
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
      if (level is List && level.length > 1) {
        total += _number(level[1]) ?? 0;
      }
    }
    return total;
  }

  void _scheduleReconnect(int generation) {
    if (_disposed || generation != _generation) return;
    _socket = null;
    _snapshot = _snapshot.copyWith(connected: false);
    _emit();
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      _open(generation);
    });
  }

  void _emit() {
    if (!_controller.isClosed) _controller.add(_snapshot);
  }

  Future<void> _closeSocket() async {
    final socket = _socket;
    _socket = null;
    if (socket != null) {
      try {
        await socket.close(WebSocketStatus.normalClosure);
      } catch (_) {
        // Socket may already have disconnected.
      }
    }
  }

  Future<void> disconnect() async {
    _generation++;
    _reconnectTimer?.cancel();
    await _closeSocket();
    _snapshot = _snapshot.copyWith(connected: false);
    _emit();
  }

  Future<void> dispose() async {
    _disposed = true;
    _generation++;
    _reconnectTimer?.cancel();
    await _closeSocket();
    await _controller.close();
  }
}
