
import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'services/analysis_api.dart';

const bg = Color(0xFF080D18), panel = Color(0xFF111A2A), soft = Color(0xFF19263A);
const line = Color(0xFF293950), muted = Color(0xFF91A2B8);
const green = Color(0xFF25D6A2), red = Color(0xFFFF647C), blue = Color(0xFF65A9FF);

void main() => runApp(const CryptoAIApp());

class CryptoAIApp extends StatelessWidget {
  const CryptoAIApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Crypto AI Intelligence', debugShowCheckedModeBanner: false,
    theme: ThemeData(
      brightness: Brightness.dark, scaffoldBackgroundColor: bg,
      colorScheme: const ColorScheme.dark(primary: green, secondary: blue, surface: panel),
      useMaterial3: true,
      cardTheme: const CardThemeData(
        color: panel, elevation: 0, margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(17)),
          side: BorderSide(color: line, width: .7))),
    ),
    home: const DashboardShell(),
  );
}

class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key, this.loadAnalysis, this.loadNotifications});
  final Future<Map<String, dynamic>> Function()? loadAnalysis;
  final Future<List<Map<String, dynamic>>> Function()? loadNotifications;
  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> with WidgetsBindingObserver {
  final api = AnalysisApi();
  late Future<Map<String, dynamic>> analysis;
  late Future<List<Map<String, dynamic>>> notifications;
  Timer? poller;
  bool refreshing = false;
  Future<Map<String, dynamic>> load() => widget.loadAnalysis?.call() ?? api.fetchIntelligence();
  Future<List<Map<String, dynamic>>> loadNotes() => widget.loadNotifications?.call() ?? api.fetchNotifications();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    analysis = load();
    notifications = loadNotes();
    startPolling();
  }

  void startPolling() {
    poller?.cancel();
    poller = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() => notifications = loadNotes());
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      setState(() { analysis = load(); notifications = loadNotes(); });
      startPolling();
    } else if (state == AppLifecycleState.paused || state == AppLifecycleState.detached) {
      poller?.cancel();
      poller = null;
    }
  }

  Future<void> refresh() async {
    if (refreshing) return;
    setState(() { refreshing = true; analysis = load(); notifications = loadNotes(); });
    try { await analysis; } finally { if (mounted) setState(() => refreshing = false); }
  }

  Future<void> markRead(int id) async {
    await api.markNotificationRead(id);
    if (mounted) setState(() => notifications = loadNotes());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    poller?.cancel();
    api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(child: FutureBuilder<Map<String, dynamic>>(
      future: analysis,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting && !snap.hasData) {
          return const Center(child: CircularProgressIndicator(color: green));
        }
        if (snap.hasError) return _ErrorView(message: snap.error.toString(), retry: refresh);
        if (snap.data == null) return _ErrorView(message: 'API belum mengirimkan data.', retry: refresh);
        return _Dashboard(data: snap.data!, notes: notifications, refreshing: refreshing,
          refresh: refresh, markRead: markRead);
      },
    )),
  );
}

class _Dashboard extends StatelessWidget {
  const _Dashboard({required this.data, required this.notes, required this.refreshing,
    required this.refresh, required this.markRead});
  final Map<String, dynamic> data;
  final Future<List<Map<String, dynamic>>> notes;
  final bool refreshing;
  final Future<void> Function() refresh;
  final Future<void> Function(int) markRead;

  @override
  Widget build(BuildContext context) {
    final side = txt(data['side'], 'NO TRADE').toUpperCase();
    final accent = side == 'BUY' ? green : side == 'SELL' ? red : blue;
    final score = number(data['confluence_score']);
    final maxScore = math.max(1, number(data['max_confluence'], 1));
    final ratio = (score / maxScore).clamp(0.0, 1.0);
    final timeframes = maps(data['timeframe_analyses']);
    final agg = mapVal(data['aggtrades_order_flow']);
    final flow = agg.isNotEmpty ? agg : mapVal(data['order_flow']);
    final market = mapVal(data['market_context']);
    final deriv = mapVal(data['derivatives']);

    return RefreshIndicator(
      onRefresh: refresh, color: green, backgroundColor: panel,
      child: CustomScrollView(physics: const AlwaysScrollableScrollPhysics(), slivers: [
        SliverPadding(padding: const EdgeInsets.fromLTRB(17, 10, 17, 28),
          sliver: SliverList(delegate: SliverChildListDelegate([
            Row(children: [
              Container(width: 42, height: 42,
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(13),
                  gradient: const LinearGradient(colors: [Color(0xFF1B9D85), Color(0xFF1761A8)])),
                child: const Icon(Icons.auto_graph_rounded, color: Colors.white)),
              const SizedBox(width: 10),
              const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('CRYPTO AI', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.2, fontSize: 15)),
                Text('INTELLIGENCE TERMINAL', style: TextStyle(color: muted, fontSize: 9, letterSpacing: 1.4)),
              ])),
              Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
                decoration: BoxDecoration(color: green.withValues(alpha: .09),
                  borderRadius: BorderRadius.circular(20), border: Border.all(color: green.withValues(alpha: .25))),
                child: const Row(children: [
                  Icon(Icons.circle, size: 7, color: green), SizedBox(width: 5),
                  Text('API ONLINE', style: TextStyle(color: green, fontSize: 9, fontWeight: FontWeight.bold)),
                ])),
              IconButton(onPressed: refreshing ? null : refresh,
                icon: refreshing ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.refresh_rounded)),
            ]),
            const SizedBox(height: 22),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('MARKET OVERVIEW', style: TextStyle(color: muted, fontSize: 10, letterSpacing: 1.5)),
                const SizedBox(height: 4),
                Text(txt(data['symbol'], 'BTCUSDT'), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900)),
                const Text('Spot market • Binance public data', style: TextStyle(color: muted, fontSize: 10)),
              ])),
              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                const Text('ANALYSIS TIME', style: TextStyle(color: muted, fontSize: 9, letterSpacing: 1)),
                const SizedBox(height: 5),
                Text(formatTime(txt(data['timestamp'], '')), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
              ]),
            ]),
            const SizedBox(height: 15),
            Container(padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(20),
                gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [accent.withValues(alpha: .18), panel, panel]),
                border: Border.all(color: accent.withValues(alpha: .45))),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Expanded(child: Text('AI MARKET BIAS', style: TextStyle(color: muted, fontSize: 10, letterSpacing: 1.3))),
                  Icon(Icons.auto_awesome, color: accent, size: 14), const SizedBox(width: 5),
                  Text('RULE-BASED ENGINE', style: TextStyle(color: accent, fontSize: 8, fontWeight: FontWeight.bold)),
                ]),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(side, style: TextStyle(color: accent, fontSize: 36, fontWeight: FontWeight.w900, letterSpacing: 1)),
                    Text(side == 'BUY' ? 'Bullish confluence' : side == 'SELL' ? 'Bearish confluence' : 'Konfirmasi belum cukup',
                      style: const TextStyle(color: muted, fontSize: 11)),
                  ])),
                  SizedBox(width: 76, height: 76, child: Stack(fit: StackFit.expand, children: [
                    CircularProgressIndicator(value: ratio, strokeWidth: 7,
                      backgroundColor: Colors.white.withValues(alpha: .07),
                      valueColor: AlwaysStoppedAnimation(accent), strokeCap: StrokeCap.round),
                    Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Text(score.toString(), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
                      const Text('SCORE', style: TextStyle(color: muted, fontSize: 8, letterSpacing: 1)),
                    ])),
                  ])),
                ]),
                const SizedBox(height: 14),
                ClipRRect(borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(value: ratio, minHeight: 5,
                    backgroundColor: Colors.white.withValues(alpha: .07), valueColor: AlwaysStoppedAnimation(accent))),
                const SizedBox(height: 8),
                Text(score.toString() + ' dari ' + maxScore.toString() + ' poin konfluensi',
                  style: const TextStyle(color: muted, fontSize: 9)),
                if (txt(data['score_note'], '').isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(txt(data['score_note'], ''), style: const TextStyle(fontSize: 10, color: Color(0xFFD1DBE8), height: 1.4)),
                ],
              ])),
            const SizedBox(height: 22),
            const _Heading('MULTI-TIMEFRAME', 'Konfirmasi arah dari beberapa kerangka waktu'),
            const SizedBox(height: 9),
            if (timeframes.isEmpty) const _Empty('Data timeframe belum tersedia.')
              else ...timeframes.map((item) => Padding(padding: const EdgeInsets.only(bottom: 8), child: _Timeframe(data: item))),
            const SizedBox(height: 15),
            const _Heading('MARKET STRUCTURE', 'Struktur harga dan zona teknikal'),
            const SizedBox(height: 9),
            _Structure(data: mapVal(data['structure'])),
            const SizedBox(height: 15),
            const _Heading('ORDER FLOW', 'Tekanan transaksi buyer dan seller'),
            const SizedBox(height: 9),
            _OrderFlow(data: flow),
            const SizedBox(height: 9),
            _Cvd(points: maps(agg['cvd_points']), scope: txt(agg['cvd_scope'], 'unavailable')),
            const SizedBox(height: 15),
            const _Heading('DERIVATIVES & LIQUIDITY', 'Konteks futures dan kondisi likuiditas'),
            const SizedBox(height: 9),
            _Derivatives(data: deriv),
            const SizedBox(height: 9),
            Row(children: [
              Expanded(child: _InfoCard(title: 'ORDER BOOK', value: txt(mapVal(market['order_book'])['bias'], 'UNAVAILABLE'),
                note: txt(mapVal(market['order_book'])['note'], 'Snapshot bid/ask'))),
              const SizedBox(width: 8),
              Expanded(child: _InfoCard(title: 'LIQUIDATIONS', value: txt(mapVal(market['liquidations'])['bias'], 'CONTEXT'),
                note: txt(mapVal(market['liquidations'])['note'], 'Riwayat teramati'))),
            ]),
            const SizedBox(height: 15),
            const _Heading('AI DECISION NOTES', 'Alasan yang mendasari keputusan sistem'),
            const SizedBox(height: 9),
            _TextCard(items: strings(data['reasons']), empty: 'Belum ada alasan sinyal yang memenuhi syarat.'),
            const SizedBox(height: 9),
            _TextCard(title: 'Market context', items: strings(data['context_notes']), empty: 'Tidak ada catatan tambahan.'),
            const SizedBox(height: 15),
            const _Heading('SIGNAL INBOX', 'Notifikasi yang tersimpan di backend'),
            const SizedBox(height: 9),
            _Inbox(future: notes, markRead: markRead),
            const SizedBox(height: 18),
            Container(padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: soft, borderRadius: BorderRadius.circular(12), border: Border.all(color: line)),
              child: const Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(Icons.shield_outlined, color: muted, size: 17), SizedBox(width: 8),
                Expanded(child: Text('Research & decision support only. Data dapat terlambat atau tidak tersedia. Sinyal bukan jaminan profit dan aplikasi tidak mengeksekusi transaksi.',
                  style: TextStyle(color: muted, fontSize: 9, height: 1.45))),
              ])),
          ]))),
        ]),
    );
  }
}

class _Heading extends StatelessWidget {
  const _Heading(this.title, this.subtitle);
  final String title, subtitle;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: 1.1)),
    const SizedBox(height: 3), Text(subtitle, style: const TextStyle(color: muted, fontSize: 9)),
  ]);
}

class _Timeframe extends StatelessWidget {
  const _Timeframe({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final side = txt(data['side'], 'UNKNOWN').toUpperCase();
    final color = side == 'BUY' ? green : side == 'SELL' ? red : blue;
    final ind = mapVal(data['indicators']);
    return Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(children: [
      Row(children: [
        Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
          decoration: BoxDecoration(color: soft, borderRadius: BorderRadius.circular(6)),
          child: Text(txt(data['timeframe'], '--').toUpperCase(), style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold))),
        const Spacer(), Text(side, style: TextStyle(color: color, fontWeight: FontWeight.w900, fontSize: 11)),
        const SizedBox(width: 10),
        Text(number(data['confluence_score']).toString() + '/' + number(data['max_confluence']).toString(),
          style: const TextStyle(color: muted, fontSize: 9)),
      ]),
      const SizedBox(height: 11),
      Row(children: [
        _Metric(label: 'LAST PRICE', value: price(ind['last_price'])),
        _Metric(label: 'RSI 14', value: decimal(ind['rsi14'])),
        _Metric(label: 'EMA 20', value: price(ind['ema20'])),
        _Metric(label: 'EMA 50', value: price(ind['ema50'])),
      ]),
      if (strings(data['reasons']).isNotEmpty) ...[
        const SizedBox(height: 8),
        Align(alignment: Alignment.centerLeft, child: Text(strings(data['reasons']).take(2).join(' • '),
          style: const TextStyle(color: muted, fontSize: 9))),
      ],
    ])));
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) => Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(label, style: const TextStyle(color: muted, fontSize: 7.5)),
    const SizedBox(height: 4), Text(value, maxLines: 1, overflow: TextOverflow.ellipsis,
      style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
  ]));
}

class _Structure extends StatelessWidget {
  const _Structure({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final rows = [
      ['TREND', txt(data['trend'], 'UNAVAILABLE')],
      ['STRUCTURE EVENT', txt(data['event'], 'UNAVAILABLE')],
      ['LIQUIDITY SWEEP', txt(data['liquidity_sweep'], 'UNAVAILABLE')],
      ['SWING HIGH', price(data['last_swing_high'])],
      ['SWING LOW', price(data['last_swing_low'])],
    ];
    return Card(child: Padding(padding: const EdgeInsets.all(13), child: Column(
      children: rows.map((r) => Padding(padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Expanded(child: Text(r[0], style: const TextStyle(color: muted, fontSize: 8, letterSpacing: .6))),
          Text(r[1], style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
        ]))).toList(),
    )));
  }
}

class _OrderFlow extends StatelessWidget {
  const _OrderFlow({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final buy = doubleVal(data['buy_aggressor_volume'] ?? data['buy_volume']);
    final sell = doubleVal(data['sell_aggressor_volume'] ?? data['sell_volume']);
    final total = buy + sell;
    final ratio = total <= 0 ? .5 : buy / total;
    final delta = doubleVal(data['net_delta']);
    return Card(child: Padding(padding: const EdgeInsets.all(13), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        _BigMetric(label: 'BUY AGGRESSOR', value: compact(buy), color: green),
        _BigMetric(label: 'SELL AGGRESSOR', value: compact(sell), color: red),
        _BigMetric(label: 'NET DELTA', value: compact(delta), color: delta > 0 ? green : delta < 0 ? red : muted),
      ]),
      const SizedBox(height: 13),
      ClipRRect(borderRadius: BorderRadius.circular(7), child: Row(children: [
        Expanded(flex: math.max(1, (ratio * 1000).round()), child: Container(height: 7, color: green)),
        Expanded(flex: math.max(1, ((1-ratio) * 1000).round()), child: Container(height: 7, color: red)),
      ])),
      const SizedBox(height: 7),
      Row(children: [
        Text('BUY ' + (ratio * 100).toStringAsFixed(1) + '%', style: const TextStyle(color: green, fontSize: 8)),
        const Spacer(),
        Text('SELL ' + ((1-ratio) * 100).toStringAsFixed(1) + '%', style: const TextStyle(color: red, fontSize: 8)),
      ]),
      const SizedBox(height: 9),
      Text('Bias: ' + txt(data['bias'], 'UNAVAILABLE') + ' • Trades: ' + txt(data['trade_count'], '—'),
        style: const TextStyle(color: muted, fontSize: 9)),
      const SizedBox(height: 4),
      Text(txt(data['method_note'], 'Volume transaksi berdasarkan data yang tersedia.'),
        style: const TextStyle(color: muted, fontSize: 8, height: 1.4)),
    ])));
  }
}

class _BigMetric extends StatelessWidget {
  const _BigMetric({required this.label, required this.value, required this.color});
  final String label, value;
  final Color color;
  @override
  Widget build(BuildContext context) => Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(label, style: const TextStyle(color: muted, fontSize: 7)),
    const SizedBox(height: 5), Text(value, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w900)),
  ]));
}

class _Cvd extends StatelessWidget {
  const _Cvd({required this.points, required this.scope});
  final List<Map<String, dynamic>> points;
  final String scope;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(13), child: Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Expanded(child: Text('CVD • RECENT AGGTRADES', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold))),
        Text(scope.toUpperCase(), style: const TextStyle(color: muted, fontSize: 8)),
      ]),
      const SizedBox(height: 10),
      SizedBox(height: 85, width: double.infinity, child: points.length > 1
        ? CustomPaint(painter: _CvdPainter(points))
        : const Center(child: Text('Belum cukup titik CVD untuk grafik.', style: TextStyle(color: muted, fontSize: 9)))),
      const SizedBox(height: 6),
      Text(points.length > 1 ? 'Batch aggTrades terbaru, bukan histori sesi penuh.'
        : 'CVD historis belum tersedia secara konsisten di serverless.',
        style: const TextStyle(color: muted, fontSize: 8)),
    ],
  )));
}

class _CvdPainter extends CustomPainter {
  _CvdPainter(this.points);
  final List<Map<String, dynamic>> points;
  @override
  void paint(Canvas canvas, Size size) {
    final values = points.map((p) => doubleVal(p['cumulative_delta'])).toList();
    if (values.length < 2) return;
    final minV = values.reduce(math.min), maxV = values.reduce(math.max);
    final range = math.max(.000001, maxV - minV);
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = i / (values.length - 1) * size.width;
      final y = size.height - ((values[i] - minV) / range) * (size.height - 10) - 5;
      if (i == 0) { path.moveTo(x, y); } else { path.lineTo(x, y); }
    }
    canvas.drawPath(path, Paint()..color = blue..strokeWidth = 2..style = PaintingStyle.stroke..strokeCap = StrokeCap.round);
    final fill = Path.from(path)..lineTo(size.width, size.height)..lineTo(0, size.height)..close();
    canvas.drawPath(fill, Paint()..shader = LinearGradient(
      colors: [blue.withValues(alpha: .2), blue.withValues(alpha: .01)],
      begin: Alignment.topCenter, end: Alignment.bottomCenter).createShader(Offset.zero & size));
  }
  @override
  bool shouldRepaint(covariant _CvdPainter oldDelegate) => oldDelegate.points != points;
}

class _Derivatives extends StatelessWidget {
  const _Derivatives({required this.data});
  final Map<String, dynamic> data;
  @override
  Widget build(BuildContext context) {
    final available = txt(data['source_market'], 'unavailable') != 'unavailable';
    return Card(child: Padding(padding: const EdgeInsets.all(13), child: Column(children: [
      Row(children: [
        _Metric(label: 'OPEN INTEREST', value: available ? compact(doubleVal(data['open_interest'])) : 'N/A'),
        _Metric(label: 'OI CHANGE', value: data['open_interest_change_percent'] == null ? 'N/A' : decimal(data['open_interest_change_percent']) + '%'),
        _Metric(label: 'FUNDING RATE', value: available ? decimal(doubleVal(data['funding_rate']) * 100) + '%' : 'N/A'),
      ]),
      const SizedBox(height: 10),
      Align(alignment: Alignment.centerLeft, child: Text(available
        ? 'Source: ' + txt(data['source_market'])
        : 'Data derivatif tidak tersedia. Placeholder tidak digunakan sebagai konfirmasi.',
        style: const TextStyle(color: muted, fontSize: 8, height: 1.4))),
    ])));
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.title, required this.value, required this.note});
  final String title, value, note;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(11), child: Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(color: muted, fontSize: 8, letterSpacing: .5)),
      const SizedBox(height: 6), Text(value, maxLines: 1, overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900)),
      const SizedBox(height: 4), Text(note, maxLines: 2, overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: muted, fontSize: 8)),
    ])));
}

class _TextCard extends StatelessWidget {
  const _TextCard({required this.items, required this.empty, this.title});
  final List<String> items;
  final String empty;
  final String? title;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (title != null) ...[Text(title!, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)), const SizedBox(height: 6)],
      if (items.isEmpty) Text(empty, style: const TextStyle(color: muted, fontSize: 9))
      else ...items.map((item) => Padding(padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(padding: EdgeInsets.only(top: 4), child: Icon(Icons.circle, size: 5, color: blue)),
          const SizedBox(width: 8), Expanded(child: Text(item,
            style: const TextStyle(fontSize: 9, height: 1.4, color: Color(0xFFD2DCE9)))),
        ]))),
    ])));
}

class _Inbox extends StatelessWidget {
  const _Inbox({required this.future, required this.markRead});
  final Future<List<Map<String, dynamic>>> future;
  final Future<void> Function(int) markRead;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(10),
    child: FutureBuilder<List<Map<String, dynamic>>>(future: future, builder: (context, snap) {
      if (snap.connectionState == ConnectionState.waiting) return const LinearProgressIndicator(minHeight: 2);
      if (snap.hasError) return Text('Inbox belum tersedia: ' + snap.error.toString(), style: const TextStyle(color: muted, fontSize: 9));
      final items = snap.data ?? [];
      if (items.isEmpty) return const Text('Belum ada notifikasi sinyal.', style: TextStyle(color: muted, fontSize: 9));
      return Column(children: items.take(8).map((item) {
        final id = item['id'] is int ? item['id'] as int : null;
        final read = item['read'] == true;
        return ListTile(contentPadding: EdgeInsets.zero, dense: true,
          leading: Icon(read ? Icons.notifications_none : Icons.notifications_active, color: read ? muted : green),
          title: Text(txt(item['title'], 'Signal alert'), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
          subtitle: Text(txt(item['message'], ''), maxLines: 2, overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: muted, fontSize: 8)),
          trailing: read ? const Icon(Icons.done, color: muted, size: 15)
            : IconButton(onPressed: id == null ? null : () => markRead(id),
              icon: const Icon(Icons.mark_email_read_outlined, size: 17)));
      }).toList());
    })));
}

class _Empty extends StatelessWidget {
  const _Empty(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(13),
    child: Text(text, style: const TextStyle(color: muted, fontSize: 9))));
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.retry});
  final String message;
  final Future<void> Function() retry;
  @override
  Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(24),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.cloud_off_rounded, color: red, size: 42), const SizedBox(height: 12),
      const Text('Market data unavailable', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8), Text(message, textAlign: TextAlign.center,
        style: const TextStyle(color: muted, fontSize: 10)),
      const SizedBox(height: 16), FilledButton.icon(onPressed: retry,
        icon: const Icon(Icons.refresh), label: const Text('Coba lagi')),
    ])));
}

String txt(dynamic v, [String fallback = '—']) {
  if (v == null) return fallback;
  final s = v.toString().trim();
  return s.isEmpty || s == 'null' ? fallback : s;
}
int number(dynamic v, [int fallback = 0]) {
  if (v is num) return v.round();
  return int.tryParse(v?.toString() ?? '') ?? fallback;
}
double doubleVal(dynamic v) {
  if (v is num) return v.toDouble();
  return double.tryParse(v?.toString() ?? '') ?? 0;
}
String decimal(dynamic v) => doubleVal(v).toStringAsFixed(2);
String price(dynamic v) {
  if (v == null) return 'N/A';
  final n = doubleVal(v);
  return n == 0 ? 'N/A' : n.toStringAsFixed(n >= 100 ? 2 : 4);
}
String compact(double n) {
  if (n.abs() >= 1000000) return (n / 1000000).toStringAsFixed(2) + 'M';
  if (n.abs() >= 1000) return (n / 1000).toStringAsFixed(2) + 'K';
  return n.toStringAsFixed(2);
}
String formatTime(String value) {
  final d = DateTime.tryParse(value)?.toLocal();
  if (d == null) return '—';
  String two(int n) => n.toString().padLeft(2, '0');
  return two(d.day) + '/' + two(d.month) + ' ' + two(d.hour) + ':' + two(d.minute);
}
Map<String, dynamic> mapVal(dynamic v) => v is Map<String, dynamic> ? v : <String, dynamic>{};
List<Map<String, dynamic>> maps(dynamic v) => v is List ? v.whereType<Map<String, dynamic>>().toList() : <Map<String, dynamic>>[];
List<String> strings(dynamic v) => v is List ? v.map((e) => e.toString()).toList() : <String>[];
