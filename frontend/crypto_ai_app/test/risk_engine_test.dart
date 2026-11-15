import 'package:crypto_ai_app/risk_engine.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('RiskCalculator', () {
    test('calculates BUY size from risk budget and stop distance', () {
      final plan = RiskCalculator.calculate(
        side: 'BUY',
        accountBalance: 1000,
        riskPercent: 1,
        entry: 100,
        stopLoss: 95,
        maxCapitalAllocationPercent: 100,
      );

      expect(plan.riskBudget, 10);
      expect(plan.quantity, 2);
      expect(plan.notional, 200);
      expect(plan.estimatedLossAtStop, 10);
      expect(plan.effectiveRiskPercent, 1);
      expect(plan.cappedByCapital, isFalse);
    });

    test('caps size by maximum capital allocation', () {
      final plan = RiskCalculator.calculate(
        side: 'BUY',
        accountBalance: 1000,
        riskPercent: 1,
        entry: 100,
        stopLoss: 95,
        maxCapitalAllocationPercent: 10,
      );

      expect(plan.quantity, 1);
      expect(plan.notional, 100);
      expect(plan.estimatedLossAtStop, 5);
      expect(plan.effectiveRiskPercent, 0.5);
      expect(plan.cappedByCapital, isTrue);
    });

    test('supports SELL with stop above entry', () {
      final plan = RiskCalculator.calculate(
        side: 'SELL',
        accountBalance: 1000,
        riskPercent: 1,
        entry: 100,
        stopLoss: 105,
        maxCapitalAllocationPercent: 100,
      );
      expect(plan.quantity, 2);
      expect(plan.estimatedLossAtStop, 10);
    });

    test('rejects risk above 2 percent', () {
      expect(
        () => RiskCalculator.calculate(
          side: 'BUY',
          accountBalance: 1000,
          riskPercent: 2.1,
          entry: 100,
          stopLoss: 95,
        ),
        throwsArgumentError,
      );
    });

    test('rejects stop loss on the wrong side', () {
      expect(
        () => RiskCalculator.calculate(
          side: 'BUY',
          accountBalance: 1000,
          riskPercent: 1,
          entry: 100,
          stopLoss: 105,
        ),
        throwsArgumentError,
      );
    });
  });
}
