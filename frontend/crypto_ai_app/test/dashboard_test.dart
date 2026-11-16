import 'package:crypto_ai_app/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders live analysis decision from API payload', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: DashboardShell(
        loadNotifications: () async => [],
        loadAnalysis: () async => {
          'symbol': 'BTCUSDT',
          'side': 'NO TRADE',
          'confluence_score': 1,
          'max_confluence': 5,
          'score_note': 'Not enough confirmation.',
          'reasons': ['Trend is mixed.'],
          'context_notes': ['Order book unavailable.'],
        },
      ),
    ));

    await tester.pumpAndSettle();
    expect(find.text('BTCUSDT'), findsOneWidget);
    expect(find.text('NO TRADE'), findsOneWidget);
    await tester.drag(find.byType(CustomScrollView), const Offset(0, -1000));
    await tester.pumpAndSettle();
    expect(find.text('Trend is mixed.'), findsOneWidget);
    await tester.drag(find.byType(CustomScrollView), const Offset(0, -900));
    await tester.pumpAndSettle();
    expect(find.text('Order book unavailable.'), findsOneWidget);
  });

  testWidgets('shows recoverable state when API fails', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: DashboardShell(
        loadNotifications: () async => [],
        loadAnalysis: () async => throw Exception('Connection refused'),
      ),
    ));

    await tester.pumpAndSettle();
    expect(find.text('Market data unavailable'), findsOneWidget);
    expect(find.text('Coba lagi'), findsOneWidget);
  });
}
