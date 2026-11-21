import 'package:crypto_ai_app/risk_calculator_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('calculates a sample linear position from manual inputs', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RiskCalculatorPage()));

    await tester.enterText(find.byKey(const ValueKey('balance')), '1000');
    await tester.enterText(find.byKey(const ValueKey('entry')), '100');
    await tester.enterText(find.byKey(const ValueKey('stop')), '95');
    await tester.pump();

    expect(find.text('Kuantitas linear estimasi'), findsOneWidget);
    expect(find.text('2.00000000 unit'), findsOneWidget);
    expect(find.text('10.00 USDT'), findsNWidgets(2));
  });

  testWidgets('prefills a SELL plan and calculates its reward risk', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: RiskCalculatorPage(
        symbol: 'BTCUSDT',
        initialSide: 'SELL',
        initialEntry: 100,
        initialStopLoss: 105,
        initialTakeProfit: 90,
      ),
    ));

    expect(tester.widget<TextField>(find.byKey(const ValueKey('entry'))).controller!.text, '100.0');
    expect(tester.widget<TextField>(find.byKey(const ValueKey('stop'))).controller!.text, '105.0');
    expect(tester.widget<TextField>(find.byKey(const ValueKey('target'))).controller!.text, '90.0');

    await tester.enterText(find.byKey(const ValueKey('balance')), '1000');
    await tester.pump();

    expect(find.text('Kalkulator Risiko • BTCUSDT'), findsOneWidget);
    expect(find.text('SELL / Short'), findsOneWidget);
    expect(find.text('Risk/Reward'), findsOneWidget);
    expect(find.text('1:2.00'), findsOneWidget);
  });

  testWidgets('shows validation when BUY stop is above entry', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RiskCalculatorPage()));

    await tester.enterText(find.byKey(const ValueKey('balance')), '1000');
    await tester.enterText(find.byKey(const ValueKey('entry')), '100');
    await tester.enterText(find.byKey(const ValueKey('stop')), '105');
    await tester.pump();

    expect(find.textContaining('stop loss di sisi yang benar'), findsOneWidget);
  });

  testWidgets('flags a target that is on the wrong side', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: RiskCalculatorPage(
        initialSide: 'BUY',
        initialEntry: 100,
        initialStopLoss: 95,
        initialTakeProfit: 90,
      ),
    ));

    await tester.enterText(find.byKey(const ValueKey('balance')), '1000');
    await tester.pump();

    expect(find.textContaining('Target tidak valid'), findsOneWidget);
  });
}
