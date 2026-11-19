import 'dart:async';
import 'dart:convert';
import 'dart:io';

class BinanceLiquidationEvent {
  const BinanceLiquidationEvent({
    required this.symbol,
    required this.side,
    required this.orderType,
    required this.status,
    required this.price,
    required this.averagePrice,
    required this.originalQuantity,
    required this.executedQuantity,
    required this.eventTimeMs,
    required this.tradeTimeMs,
  });

  final String symbol;
  final String side;
  final String orderType;
  final String status;
  final double price;
  final double averagePrice;
  final double originalQuantity;
  final double executedQuantity;
  final int eventTimeMs;
  final int tradeTimeMs;

  double get executedNotional => averagePrice * executedQuantity;

  String get sideDescription => side == 'SELL'
      ? 'SELL • umumnya menutup posisi LONG'
      : 'BUY • umumnya menutup posisi SHORT';

  static BinanceLiquidationEvent fromJson(Map<String, dynamic> json) {
    if (json['e'] != 'forceOrder') {
      throw const FormatException('Event bukan forceOrder.');
    }
    final rawOrder = json['o'];
    if (rawOrder is! Map) {
      throw const FormatException('Objek order liquidation tidak tersedia.');
    }

    final symbol = rawOrder['s']?.toString().toUpperCase();
    final side = rawOrder['S']?.toString().toUpperCase();
    final orderType = rawOrder['o']?.toString() ?? 'UNKNOWN';
    final status = rawOrder['X']?.toString() ?? 'UNKNOWN';
    final price = _number(rawOrder['p']);
    final rawAveragePrice = _number(rawOrder['ap']);
    final originalQuantity = _number(rawOrder['q']);
    final executedQuantity = _number(rawOrder['z']);
    final eventTime = _integer(json['E']);
    final tradeTime = _integer(rawOrder['T']);

    if (symbol == null ||
        !RegExp(r'^[A-Z0-9]{4,30}$').hasMatch(symbol) ||
        side == null ||
        (side != 'BUY' && side != 'SELL') ||
        price == null ||
        price <= 0 ||
        rawAveragePrice == null ||
        rawAveragePrice < 0 ||
        originalQuantity == null ||
        originalQuantity <= 0 ||
        executedQuantity == null ||
        executedQuantity < 0 ||
        eventTime == null ||
        eventTime <= 0 ||
        tradeTime == null ||
        tradeTime <= 0) {
      throw const FormatException('Payload liquidation tidak valid.');
    }

    return BinanceLiquidationEvent(
      symbol: symbol,
      side: side,
      orderType: orderType,
      status: status,
      price: price,
      averagePrice: rawAveragePrice > 0 ? rawAveragePrice : price,
      originalQuantity: originalQuantity,
      executedQuantity: executedQuantity,
      eventTimeMs: eventTime,
      tradeTimeMs: tradeTime,
    );
  }

  static double? _number(dynamic value) {
    if (value is num) {
      final result = value.toDouble();
      return result.isFinite ? result : null;
    }
    if (value is String) {
      final result = double.tryParse(value);
      return result != null && result.isFinite ? result : null;
    }
    return null;
  }

  static int? _integer(dynamic value) {
    if (value is int) return value;
    if (value is num && value.isFinite) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }
}

enum LiquidationFeedStatus {
  disconnected,
  connecting,
  connected,
  reconnecting,
  error,
}

class LiquidationFeedState {
  const LiquidationFeedState(this.status, {this.message});

  final LiquidationFeedStatus status;
  final String? message;
}

/// Public Binance USDⓈ-M Futures liquidation stream; no API key is required.
class BinanceLiquidationFeed {
  final StreamController<BinanceLiquidationEvent> _events =
      StreamController<BinanceLiquidationEvent>.broadcast();
  final StreamController<LiquidationFeedState> _states =
      StreamController<LiquidationFeedState>.broadcast();

  WebSocket? _socket;
  StreamSubscription<dynamic>? _subscription;
  Timer? _reconnectTimer;
  String? _symbol;
  int _generation = 0;
  int _retryCount = 0;
  bool _disposed = false;

  Stream<BinanceLiquidationEvent> get events => _events.stream;
  Stream<LiquidationFeedState> get states => _states.stream;

  void _setState(LiquidationFeedStatus status, String message) {
    if (!_disposed && !_states.isClosed) {
      _states.add(LiquidationFeedState(status, message: message));
    }
  }

  Future<void> connect(String symbol) async {
    if (_disposed) return;
    final normalized = symbol.trim().toUpperCase();
    if (!RegExp(r'^[A-Z0-9]{4,30}$').hasMatch(normalized)) {
      _setState(LiquidationFeedStatus.error, 'Simbol liquidation tidak valid.');
      return;
    }

    final generation = ++_generation;
    _symbol = normalized;
    _retryCount = 0;
    _reconnectTimer?.cancel();
    await _closeSocket();
    if (_disposed || generation != _generation) return;

    _setState(
      LiquidationFeedStatus.connecting,
      'Menghubungkan stream liquidation $normalized...',
    );
    unawaited(_open(generation));
  }

  Future<void> _open(int generation) async {
    final symbol = _symbol;
    if (_disposed || symbol == null || generation != _generation) return;

    final uri = Uri.parse(
      'wss://fstream.binance.com/market/ws/${symbol.toLowerCase()}@forceOrder',
    );
    try {
      final socket = await WebSocket.connect(uri.toString())
          .timeout(const Duration(seconds: 12));
      if (_disposed || generation != _generation) {
        await socket.close();
        return;
      }

      _socket = socket;
      _retryCount = 0;
      socket.pingInterval = const Duration(seconds: 20);
      _setState(
        LiquidationFeedStatus.connected,
        'Stream $symbol terhubung; menunggu snapshot liquidation.',
      );
      _subscription = socket.listen(
        (dynamic message) => _handleMessage(message, generation),
        onError: (Object error) =>
            _scheduleReconnect(generation, 'WebSocket error: $error'),
        onDone: () =>
            _scheduleReconnect(generation, 'Koneksi Binance ditutup.'),
        cancelOnError: true,
      );
    } catch (error) {
      _scheduleReconnect(generation, 'Gagal menghubungkan: $error');
    }
  }

  void _handleMessage(dynamic message, int generation) {
    if (_disposed || generation != _generation) return;
    try {
      final decoded = jsonDecode(message.toString());
      if (decoded is! Map<String, dynamic>) return;
      final event = BinanceLiquidationEvent.fromJson(decoded);
      if (event.symbol == _symbol && !_events.isClosed) {
        _events.add(event);
      }
    } on FormatException {
      // Abaikan payload non-liquidation atau payload yang tidak lengkap.
    }
  }

  void _scheduleReconnect(int generation, String reason) {
    if (_disposed ||
        generation != _generation ||
        (_reconnectTimer?.isActive ?? false)) {
      return;
    }

    unawaited(_closeSocket());
    _retryCount++;
    final delaySeconds = _retryCount >= 5
        ? 30
        : 3 * (1 << (_retryCount - 1));
    _setState(
      LiquidationFeedStatus.reconnecting,
      '$reason Mencoba lagi dalam ${delaySeconds}s.',
    );
    _reconnectTimer = Timer(Duration(seconds: delaySeconds), () {
      _reconnectTimer = null;
      unawaited(_open(generation));
    });
  }

  Future<void> _closeSocket() async {
    final subscription = _subscription;
    _subscription = null;
    if (subscription != null) await subscription.cancel();

    final socket = _socket;
    _socket = null;
    if (socket != null) {
      try {
        await socket.close(WebSocketStatus.normalClosure);
      } catch (_) {
        // Socket may already be closed by Binance or the network.
      }
    }
  }

  Future<void> disconnect() async {
    _generation++;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    await _closeSocket();
    _setState(LiquidationFeedStatus.disconnected, 'Stream liquidation terputus.');
  }

  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _generation++;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    await _closeSocket();
    await _events.close();
    await _states.close();
  }
}
