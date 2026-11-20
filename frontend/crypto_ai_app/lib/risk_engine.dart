/// Linear price-risk estimate only. This module never places orders.
/// It does not model exchange contract multipliers, leverage, margin, fees,
/// funding, spread, slippage, tick size, lot size, or liquidation price.

class PositionPlan {
  final double riskBudget;
  final double quantity;
  final double notional;
  final double estimatedLossAtStop;
  final double effectiveRiskPercent;
  final double capitalAllocationPercent;
  final bool cappedByCapital;

  const PositionPlan({
    required this.riskBudget,
    required this.quantity,
    required this.notional,
    required this.estimatedLossAtStop,
    required this.effectiveRiskPercent,
    required this.capitalAllocationPercent,
    required this.cappedByCapital,
  });
}

class RiskCalculator {
  /// Estimates base-unit quantity from account risk and entry-to-stop distance.
  /// Risk is hard-limited to 2%; notional is capped by the selected percentage
  /// of the entered quote balance. This is not exchange-ready futures sizing.
  static PositionPlan calculate({
    required String side,
    required double accountBalance,
    required double riskPercent,
    required double entry,
    required double stopLoss,
    double maxCapitalAllocationPercent = 20,
  }) {
    final normalizedSide = side.toUpperCase();
    if (normalizedSide != 'BUY' && normalizedSide != 'SELL') {
      throw ArgumentError('Sisi harus BUY atau SELL');
    }
    if (!_isPositiveFinite(accountBalance) ||
        !_isPositiveFinite(entry) ||
        !_isPositiveFinite(stopLoss)) {
      throw ArgumentError('Saldo, entry, dan stop loss harus angka positif');
    }
    if (!_isPositiveFinite(riskPercent) || riskPercent > 2) {
      throw ArgumentError('Risiko per transaksi harus lebih dari 0% dan maksimal 2%');
    }
    if (!_isPositiveFinite(maxCapitalAllocationPercent) ||
        maxCapitalAllocationPercent > 100) {
      throw ArgumentError('Batas notional harus lebih dari 0% dan maksimal 100%');
    }

    final validStop = normalizedSide == 'BUY'
        ? stopLoss < entry
        : stopLoss > entry;
    if (!validStop) {
      throw ArgumentError('Posisi $normalizedSide membutuhkan stop loss di sisi yang benar');
    }

    final stopDistance = (entry - stopLoss).abs();
    final riskBudget = accountBalance * riskPercent / 100;
    final requestedQuantity = riskBudget / stopDistance;
    final notionalLimit = accountBalance * maxCapitalAllocationPercent / 100;
    final maxQuantityByNotional = notionalLimit / entry;
    final quantity = requestedQuantity < maxQuantityByNotional
        ? requestedQuantity
        : maxQuantityByNotional;

    if (!_isPositiveFinite(quantity)) {
      throw ArgumentError('Ukuran posisi tidak valid');
    }

    final notional = quantity * entry;
    final estimatedLossAtStop = quantity * stopDistance;
    return PositionPlan(
      riskBudget: riskBudget,
      quantity: quantity,
      notional: notional,
      estimatedLossAtStop: estimatedLossAtStop,
      effectiveRiskPercent: estimatedLossAtStop / accountBalance * 100,
      capitalAllocationPercent: notional / accountBalance * 100,
      cappedByCapital: quantity < requestedQuantity,
    );
  }

  /// Returns reward divided by risk, e.g. 2.0 means 1:2.
  /// The target must be beyond entry in the intended trade direction.
  static double calculateRewardRisk({
    required String side,
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) {
    final normalizedSide = side.toUpperCase();
    if (normalizedSide != 'BUY' && normalizedSide != 'SELL') {
      throw ArgumentError('Sisi harus BUY atau SELL');
    }
    if (!_isPositiveFinite(entry) ||
        !_isPositiveFinite(stopLoss) ||
        !_isPositiveFinite(takeProfit)) {
      throw ArgumentError('Entry, stop loss, dan take profit harus angka positif');
    }

    final validStop = normalizedSide == 'BUY'
        ? stopLoss < entry
        : stopLoss > entry;
    if (!validStop) {
      throw ArgumentError('Stop loss tidak berada di sisi yang benar');
    }

    final validTarget = normalizedSide == 'BUY'
        ? takeProfit > entry
        : takeProfit < entry;
    if (!validTarget) {
      throw ArgumentError('Take profit tidak berada di sisi yang benar');
    }

    return (takeProfit - entry).abs() / (entry - stopLoss).abs();
  }

  static bool _isPositiveFinite(double value) => value.isFinite && value > 0;
}
