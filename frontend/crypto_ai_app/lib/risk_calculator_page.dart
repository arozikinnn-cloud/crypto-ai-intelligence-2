import 'package:flutter/material.dart';

import 'risk_engine.dart';

/// Manual risk calculator. It has no exchange connection or order action.
/// Optional values let a validated dashboard trade plan prefill the form.
class RiskCalculatorPage extends StatefulWidget {
  const RiskCalculatorPage({
    super.key,
    this.symbol,
    this.initialSide,
    this.initialEntry,
    this.initialStopLoss,
    this.initialTakeProfit,
  });

  final String? symbol;
  final String? initialSide;
  final double? initialEntry;
  final double? initialStopLoss;
  final double? initialTakeProfit;

  @override
  State<RiskCalculatorPage> createState() => _RiskCalculatorPageState();
}

class _RiskCalculatorPageState extends State<RiskCalculatorPage> {
  final _balanceController = TextEditingController();
  final _entryController = TextEditingController();
  final _stopController = TextEditingController();
  final _takeProfitController = TextEditingController();
  final _riskController = TextEditingController(text: '1');
  final _allocationController = TextEditingController(text: '20');
  String _side = 'BUY';

  String _initialText(double? value) => value == null ? '' : value.toString();

  @override
  void initState() {
    super.initState();
    final initialSide = widget.initialSide?.toUpperCase();
    if (initialSide == 'BUY' || initialSide == 'SELL') {
      _side = initialSide!;
    }
    _entryController.text = _initialText(widget.initialEntry);
    _stopController.text = _initialText(widget.initialStopLoss);
    _takeProfitController.text = _initialText(widget.initialTakeProfit);
  }

  @override
  void dispose() {
    _balanceController.dispose();
    _entryController.dispose();
    _stopController.dispose();
    _takeProfitController.dispose();
    _riskController.dispose();
    _allocationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final balance = double.tryParse(_balanceController.text.trim());
    final entry = double.tryParse(_entryController.text.trim());
    final stop = double.tryParse(_stopController.text.trim());
    final takeProfit = double.tryParse(_takeProfitController.text.trim());
    final risk = double.tryParse(_riskController.text.trim());
    final allocation = double.tryParse(_allocationController.text.trim());

    PositionPlan? plan;
    String? error;
    if (balance != null && entry != null && stop != null &&
        risk != null && allocation != null) {
      try {
        plan = RiskCalculator.calculate(
          side: _side,
          accountBalance: balance,
          riskPercent: risk,
          entry: entry,
          stopLoss: stop,
          maxCapitalAllocationPercent: allocation,
        );
      } on ArgumentError catch (e) {
        error = e.message?.toString() ?? 'Input tidak valid';
      }
    }

    double? rewardRisk;
    String? targetError;
    if (entry != null && stop != null && takeProfit != null) {
      try {
        rewardRisk = RiskCalculator.calculateRewardRisk(
          side: _side,
          entry: entry,
          stopLoss: stop,
          takeProfit: takeProfit,
        );
      } on ArgumentError catch (e) {
        targetError = e.message?.toString() ?? 'Target tidak valid';
      }
    } else if (_takeProfitController.text.trim().isNotEmpty && takeProfit == null) {
      targetError = 'Take profit harus berupa angka positif';
    }

    final title = widget.symbol == null
        ? 'Kalkulator Risiko'
        : 'Kalkulator Risiko • ${widget.symbol}';

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Input simulasi', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    key: const ValueKey('side'),
                    value: _side,
                    decoration: const InputDecoration(labelText: 'Arah posisi'),
                    items: const [
                      DropdownMenuItem(value: 'BUY', child: Text('BUY / Long')),
                      DropdownMenuItem(value: 'SELL', child: Text('SELL / Short')),
                    ],
                    onChanged: (value) {
                      if (value != null) setState(() => _side = value);
                    },
                  ),
                  const SizedBox(height: 8),
                  _numberField(
                    keyName: 'balance',
                    controller: _balanceController,
                    label: 'Saldo simulasi (USDT)',
                    hint: 'Contoh: 1000',
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: _numberField(
                          keyName: 'entry',
                          controller: _entryController,
                          label: 'Harga entry',
                          hint: 'Contoh: 100',
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _numberField(
                          keyName: 'stop',
                          controller: _stopController,
                          label: 'Harga stop loss',
                          hint: 'Contoh: 95',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  _numberField(
                    keyName: 'target',
                    controller: _takeProfitController,
                    label: 'Harga take profit',
                    hint: 'Diisi dari rencana AI atau manual',
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: _numberField(
                          keyName: 'risk',
                          controller: _riskController,
                          label: 'Risiko (%)',
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _numberField(
                          keyName: 'allocation',
                          controller: _allocationController,
                          label: 'Batas notional (% saldo)',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Batas simulasi: risiko maksimal 2% per perhitungan dan nilai posisi maksimal 100% dari saldo yang dimasukkan.',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Hasil perhitungan', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (plan == null)
                    Text(
                      error ?? 'Masukkan saldo, entry, dan stop loss untuk melihat estimasi ukuran posisi.',
                      key: const ValueKey('calculation-message'),
                      style: TextStyle(
                        color: error == null
                            ? Theme.of(context).colorScheme.onSurfaceVariant
                            : Theme.of(context).colorScheme.error,
                      ),
                    )
                  else ...[
                    _resultRow('Kuantitas linear estimasi', '${plan.quantity.toStringAsFixed(8)} unit'),
                    _resultRow('Nilai notional estimasi', '${plan.notional.toStringAsFixed(2)} USDT'),
                    _resultRow('Anggaran risiko', '${plan.riskBudget.toStringAsFixed(2)} USDT'),
                    _resultRow('Estimasi rugi saat SL', '${plan.estimatedLossAtStop.toStringAsFixed(2)} USDT'),
                    _resultRow('Risiko efektif saldo', '${plan.effectiveRiskPercent.toStringAsFixed(2)}%'),
                    _resultRow('Notional vs saldo', '${plan.capitalAllocationPercent.toStringAsFixed(2)}%'),
                    _resultRow('Take profit', takeProfit == null ? 'Belum diisi' : takeProfit.toString()),
                    if (rewardRisk != null)
                      _resultRow('Risk/Reward', '1:${rewardRisk.toStringAsFixed(2)}'),
                    if (targetError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          'Target tidak valid: $targetError',
                          style: TextStyle(color: Theme.of(context).colorScheme.error),
                        ),
                      ),
                    if (plan.cappedByCapital)
                      const Padding(
                        padding: EdgeInsets.only(top: 8),
                        child: Text(
                          'Nilai notional dibatasi oleh batas yang dipilih. Risiko efektif lebih kecil dari target risiko.',
                          style: TextStyle(color: Colors.orange),
                        ),
                      ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Estimasi linear teoretis untuk membantu memahami jarak risiko. Bukan ukuran order siap kirim. Belum memodelkan contract multiplier, leverage, margin, funding, fee, spread, slippage, tick/lot size, saldo exchange, atau harga likuidasi. Tidak ada API exchange dan tidak ada order yang dikirim; kerugian nyata dapat melebihi estimasi.',
            style: TextStyle(fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _numberField({
    required String keyName,
    required TextEditingController controller,
    required String label,
    String? hint,
  }) => TextField(
        key: ValueKey(keyName),
        controller: controller,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        onChanged: (_) => setState(() {}),
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
      );

  Widget _resultRow(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(child: Text(label)),
            const SizedBox(width: 12),
            Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
          ],
        ),
      );
}
