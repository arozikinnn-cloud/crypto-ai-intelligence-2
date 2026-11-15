import 'package:flutter/material.dart';

import 'risk_engine.dart';

/// Manual spot-style risk calculator. It has no exchange connection or order action.
class RiskCalculatorPage extends StatefulWidget {
  const RiskCalculatorPage({super.key});

  @override
  State<RiskCalculatorPage> createState() => _RiskCalculatorPageState();
}

class _RiskCalculatorPageState extends State<RiskCalculatorPage> {
  final _balanceController = TextEditingController();
  final _entryController = TextEditingController();
  final _stopController = TextEditingController();
  final _riskController = TextEditingController(text: '1');
  final _allocationController = TextEditingController(text: '20');
  String _side = 'BUY';

  @override
  void dispose() {
    _balanceController.dispose();
    _entryController.dispose();
    _stopController.dispose();
    _riskController.dispose();
    _allocationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final balance = double.tryParse(_balanceController.text.trim());
    final entry = double.tryParse(_entryController.text.trim());
    final stop = double.tryParse(_stopController.text.trim());
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

    return Scaffold(
      appBar: AppBar(title: const Text('Kalkulator Risiko')),
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
                      DropdownMenuItem(value: 'BUY', child: Text('BUY / Long spot')),
                      DropdownMenuItem(value: 'SELL', child: Text('SELL / aset sudah dimiliki')),
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
                          label: 'Batas modal (%)',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Batas keamanan: risiko maksimal 2% per transaksi dan alokasi modal maksimal 100%.',
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
                      error ?? 'Masukkan saldo, entry, dan stop loss untuk melihat estimasi.',
                      key: const ValueKey('calculation-message'),
                      style: TextStyle(
                        color: error == null ? Theme.of(context).colorScheme.onSurfaceVariant : Theme.of(context).colorScheme.error,
                      ),
                    )
                  else ...[
                    _resultRow('Kuantitas estimasi', '${plan.quantity.toStringAsFixed(8)} unit'),
                    _resultRow('Nilai posisi', '${plan.notional.toStringAsFixed(2)} USDT'),
                    _resultRow('Anggaran risiko', '${plan.riskBudget.toStringAsFixed(2)} USDT'),
                    _resultRow('Estimasi rugi saat SL', '${plan.estimatedLossAtStop.toStringAsFixed(2)} USDT'),
                    _resultRow('Risiko efektif saldo', '${plan.effectiveRiskPercent.toStringAsFixed(2)}%'),
                    _resultRow('Modal terpakai', '${plan.capitalAllocationPercent.toStringAsFixed(2)}%'),
                    if (plan.cappedByCapital)
                      const Padding(
                        padding: EdgeInsets.only(top: 8),
                        child: Text(
                          'Ukuran posisi dibatasi oleh alokasi modal. Risiko efektif lebih kecil dari target risiko.',
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
            'Simulasi spot saja. Tidak menghitung fee, spread, slippage, pajak, gap harga, atau saldo aset aktual. Untuk SELL, aset harus sudah dimiliki. Tidak ada API exchange dan tidak ada order yang dikirim. Kerugian nyata dapat melebihi estimasi saat eksekusi buruk.',
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
