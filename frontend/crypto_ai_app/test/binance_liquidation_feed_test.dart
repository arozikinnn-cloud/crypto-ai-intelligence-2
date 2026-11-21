import 'package:crypto_ai_app/services/binance_liquidation_feed.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('BinanceLiquidationEvent', () {
    final payload = <String, dynamic>{
      'e': 'forceOrder',
      'E': 1700000000123,
      'o': {
        's': 'BTCUSDT',
        'S': 'SELL',
        'o': 'LIMIT',
        'X': 'FILLED',
        'q': '0.014',
        'p': '9910',
        'ap': '9912.5',
        'z': '0.014',
        'T': 1700000000100,
      },
    };

    test('parses forced sell and calculates executed notional', () {
      final event = BinanceLiquidationEvent.fromJson(payload);

      expect(event.symbol, 'BTCUSDT');
      expect(event.side, 'SELL');
      expect(event.sideDescription, 'SELL • umumnya menutup posisi LONG');
      expect(event.averagePrice, 9912.5);
      expect(event.executedQuantity, 0.014);
      expect(event.executedNotional, closeTo(138.775, 1e-9));
      expect(event.tradeTimeMs, 1700000000100);
    });

    test('interprets forced buy as generally closing a short', () {
      final buyPayload = <String, dynamic>{
        ...payload,
        'o': {
          ...(payload['o'] as Map<String, dynamic>),
          'S': 'BUY',
        },
      };
      final event = BinanceLiquidationEvent.fromJson(buyPayload);

      expect(event.side, 'BUY');
      expect(event.sideDescription, 'BUY • umumnya menutup posisi SHORT');
    });

    test('rejects wrong event type, side, and invalid price', () {
      expect(
        () => BinanceLiquidationEvent.fromJson({...payload, 'e': 'aggTrade'}),
        throwsA(isA<FormatException>()),
      );

      final invalidSide = <String, dynamic>{
        ...payload,
        'o': {
          ...(payload['o'] as Map<String, dynamic>),
          'S': 'HOLD',
        },
      };
      expect(
        () => BinanceLiquidationEvent.fromJson(invalidSide),
        throwsA(isA<FormatException>()),
      );

      final invalidPrice = <String, dynamic>{
        ...payload,
        'o': {
          ...(payload['o'] as Map<String, dynamic>),
          'p': '0',
        },
      };
      expect(
        () => BinanceLiquidationEvent.fromJson(invalidPrice),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
