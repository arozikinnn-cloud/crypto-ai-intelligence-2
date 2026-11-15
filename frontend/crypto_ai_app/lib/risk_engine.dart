/// Conservative position sizing for a cash/spot-style estimate.
/// This module never places orders and does not model leverage, fees or slippage.

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
  /// Returns a theoretical base-asset quantity using the entry-to-stop distance.
  ///
  /// Risk is hard-limited to 2% per trade. The notional is also capped by
  /// [maxCapitalAllocationPercent] of the entered quote balance. For a spot
  /// SELL signal, the user must already own the base asset; balances are not
  /// fetched from an exchange.
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
      throw ArgumentError('Alokasi modal harus lebih dari 0% dan maksimal 100%');
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
    final capitalLimit = accountBalance * maxCapitalAllocationPercent / 100;
    final maxQuantityByCapital = capitalLimit / entry;
    final quantity = requestedQuantity < maxQuantityByCapital
        ? requestedQuantity
        : maxQuantityByCapital;

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

  static bool _isPositiveFinite(double value) => value.isFinite && value > 0;
}
