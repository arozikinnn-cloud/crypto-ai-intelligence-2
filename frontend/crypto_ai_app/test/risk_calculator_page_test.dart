import 'package:crypto_ai_app/risk_calculator_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('calculates a sample spot position from manual inputs', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RiskCalculatorPage()));

    await tester.enterText(find.byKey(const ValueKey('balance')), '1000');
    await tester.enterText(find.byKey(const ValueKey('entry')), '100');
    await tester.enterText(find.byKey(const ValueKey('stop')), '95');
    await tester.pump();

    expect(find.text('Kuantitas estimasi'), findsOneWidget);
    expect(find.text('2.00000000 unit'), findsOneWidget);
    expect(find.text('10.00 USDT'), findsNWidgets(2));
  });

  testWidgets('shows validation when BUY stop is above entry', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RiskCalculatorPage()));

    await tester.enterText(find.byKey(const ValueKey('balance')), '1000');
    await tester.enterText(find.byKey(const ValueKey('entry')), '100');
    await tester.enterText(find.byKey(const ValueKey('stop')), '105');
    await tester.pump();

    expect(find.textContaining('stop loss di sisi yang benar'), findsOneWidget);
  });
}
