
import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'services/analysis_api.dart';
import 'services/binance_websocket.dart';

const bg = Color(0xFF080D18), panel = Color(0xFF111A2A), soft = Color(0xFF19263A);
const line = Color(0xFF293950), muted = Color(0xFF91A2B8);
const green = Color(0xFF25D6A2), red = Color(0xFFFF647C), blue = Color(0xFF65A9FF);
const supportedSymbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];

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

class _PlanValue extends StatelessWidget {
  const _PlanValue(this.label, this.value);
  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: muted, fontSize: 8, letterSpacing: .8)),
      const SizedBox(height: 4),
      Text(value == null ? '—' : value.toString(),
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800)),
    ],
  );
}

class _Tag extends StatelessWidget {
  const _Tag(this.label);
  final String label;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
    decoration: BoxDecoration(
      color: const Color(0xFF182536),
      borderRadius: BorderRadius.circular(7),
      border: Border.all(color: line),
    ),
    child: Text(label, style: const TextStyle(color: muted, fontSize: 8, fontWeight: FontWeight.bold)),
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
  final liveFeed = BinanceWebSocketFeed();
  StreamSubscription<BinanceLiveSnapshot>? liveSubscription;
  BinanceLiveSnapshot liveSnapshot = const BinanceLiveSnapshot(connected: false);
  void startLiveFeed() {
    liveSubscription?.cancel();
    liveSubscription = liveFeed.stream.listen((snapshot) {
      if (mounted) setState(() => liveSnapshot = snapshot);
    });
    liveFeed.connect(selectedSymbol);
  }
  late Future<Map<String, dynamic>> analysis;
  late Future<List<Map<String, dynamic>>> notifications;
  late Future<List<Map<String, dynamic>>> scanner;
  late Future<List<Map<String, dynamic>>> signals;
  late Future<Map<String, dynamic>> backtest;
  late Future<Map<String, dynamic>> signalPerformance;
  late Future<List<Map<String, dynamic>>> candles;
  Timer? poller;
  Timer? analysisPoller;
  bool refreshing = false;
  String selectedSymbol = 'BTCUSDT';
  String selectedCandleInterval = '15m';
  Future<Map<String, dynamic>> load() => widget.loadAnalysis?.call() ?? api.fetchIntelligence(symbol: selectedSymbol);
  Future<List<Map<String, dynamic>>> loadCandles() async {
    try {
      return await api.fetchCandles(
        symbol: selectedSymbol,
        interval: selectedCandleInterval,
        limit: 80,
      );
    } catch (_) {
      return <Map<String, dynamic>>[];
    }
  }

  Future<void> changeCandleInterval(String interval) async {
    if (interval == selectedCandleInterval) return;
    setState(() {
      selectedCandleInterval = interval;
      candles = loadCandles();
    });
  }

  Future<void> changeSymbol(String? symbol) async {
    if (symbol == null || symbol == selectedSymbol || refreshing) return;
    setState(() { selectedSymbol = symbol; refreshing = true; analysis = load(); candles = loadCandles(); backtest = loadBacktest(); signalPerformance = loadSignalPerformance(); });
    liveFeed.connect(symbol);
    try { await analysis; } finally { if (mounted) setState(() => refreshing = false); }
  }
  Future<List<Map<String, dynamic>>> loadNotes() => widget.loadNotifications?.call() ?? api.fetchNotifications();
  Future<List<Map<String, dynamic>>> loadSignals() async {
    try {
      return await api.fetchSignals(status: 'all', limit: 50);
    } catch (_) {
      return <Map<String, dynamic>>[];
    }
  }

  Future<Map<String, dynamic>> loadSignalPerformance() async {
    try { return await api.fetchSignalPerformance(); }
    catch (error) { return <String, dynamic>{'unavailable_reason': error.toString()}; }
  }

  Future<Map<String, dynamic>> loadBacktest() async {
    try {
      return await api.fetchBacktest(symbol: selectedSymbol);
    } catch (error) {
      return <String, dynamic>{'unavailable_reason': error.toString()};
    }
  }

  Future<List<Map<String, dynamic>>> loadScanner() async {
    final results = await Future.wait(supportedSymbols.map((symbol) async {
      try {
        final result = await api.fetchIntelligence(symbol: symbol);
        return <String, dynamic>{...result, 'scanner_status': 'OK'};
      } catch (error) {
        return <String, dynamic>{'symbol': symbol, 'side': 'UNAVAILABLE', 'scanner_status': error.toString()};
      }
    }));
    return results;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    analysis = load();
    candles = loadCandles();
    notifications = loadNotes();
    scanner = loadScanner();
    signals = loadSignals();
    backtest = loadBacktest();
    signalPerformance = loadSignalPerformance();
    startPolling();
    startLiveFeed();
  }

  void startPolling() {
    poller?.cancel();
    poller = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() { notifications = loadNotes(); signals = loadSignals(); signalPerformance = loadSignalPerformance(); });
    });
    analysisPoller?.cancel();
    analysisPoller = Timer.periodic(const Duration(minutes: 5), (_) {
      if (mounted && !refreshing) setState(() { analysis = load(); candles = loadCandles(); signalPerformance = loadSignalPerformance(); });
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      setState(() { analysis = load(); candles = loadCandles(); notifications = loadNotes(); scanner = loadScanner(); signals = loadSignals(); backtest = loadBacktest(); signalPerformance = loadSignalPerformance(); });
      startPolling();
      startLiveFeed();
    } else if (state == AppLifecycleState.paused || state == AppLifecycleState.detached) {
      poller?.cancel();
      poller = null;
      analysisPoller?.cancel();
      analysisPoller = null;
      liveFeed.disconnect();
    }
  }

  Future<void> refresh() async {
    if (refreshing) return;
    setState(() { refreshing = true; analysis = load(); candles = loadCandles(); notifications = loadNotes(); scanner = loadScanner(); signals = loadSignals(); backtest = loadBacktest(); });
    try { await analysis; } finally { if (mounted) setState(() => refreshing = false); }
  }

  Future<void> markRead(int id) async {
    await api.markNotificationRead(id);
    if (mounted) setState(() => notifications = loadNotes());
  }

  Future<void> closeSignal(int id) async {
    await api.closeSignal(id);
    if (mounted) setState(() => signals = loadSignals());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    poller?.cancel();
    analysisPoller?.cancel();
    liveSubscription?.cancel();
    liveFeed.dispose();
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
          selectedSymbol: selectedSymbol, onSymbolChanged: changeSymbol,
          scanner: scanner, signals: signals, backtest: backtest, refresh: refresh, markRead: markRead,
          closeSignal: closeSignal, signalPerformance: signalPerformance, candles: candles, candleInterval: selectedCandleInterval, onCandleIntervalChanged: changeCandleInterval, liveSnapshot: liveSnapshot);
      },
    )),
  );
}

class _Dashboard extends StatelessWidget {
  const _Dashboard({required this.data, required this.notes, required this.refreshing,
    required this.selectedSymbol, required this.onSymbolChanged, required this.scanner,
    required this.signals, required this.backtest, required this.refresh, required this.markRead, required this.closeSignal, required this.signalPerformance, required this.candles, required this.candleInterval, required this.onCandleIntervalChanged, required this.liveSnapshot});
  final Map<String, dynamic> data;
  final Future<List<Map<String, dynamic>>> notes;
  final bool refreshing;
  final String selectedSymbol;
  final ValueChanged<String?> onSymbolChanged;
  final Future<List<Map<String, dynamic>>> scanner;
  final Future<List<Map<String, dynamic>>> signals;
  final Future<Map<String, dynamic>> backtest;
  final Future<void> Function() refresh;
  final Future<void> Function(int) markRead;
  final Future<void> Function(int) closeSignal;
  final Future<Map<String, dynamic>> signalPerformance;
  final Future<List<Map<String, dynamic>>> candles;
  final String candleInterval;
  final ValueChanged<String> onCandleIntervalChanged;
  final BinanceLiveSnapshot liveSnapshot;

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
    final tradePlan = mapVal(data['trade_plan']);

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
                DropdownButton<String>(
                  value: supportedSymbols.contains(selectedSymbol) ? selectedSymbol : 'BTCUSDT',
                  isDense: true, underline: const SizedBox.shrink(),
                  dropdownColor: panel, iconEnabledColor: green,
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Colors.white),
                  items: supportedSymbols.map((symbol) => DropdownMenuItem(value: symbol, child: Text(symbol))).toList(),
                  onChanged: refreshing ? null : onSymbolChanged,
                ),
                const Text('Spot market • Binance public data', style: TextStyle(color: muted, fontSize: 10)),
              ])),
              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                const Text('ANALYSIS TIME', style: TextStyle(color: muted, fontSize: 9, letterSpacing: 1)),
                const SizedBox(height: 5),
                Text(formatTime(txt(data['timestamp'], '')), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
              ]),
            ]),
            const SizedBox(height: 16),
            _Heading('$selectedSymbol / MARKET CANDLES', 'Multi-timeframe candlestick • Binance Spot'),
            const SizedBox(height: 8),
            _CandlestickChart(future: candles, interval: candleInterval, onIntervalChanged: onCandleIntervalChanged),
            const SizedBox(height: 8),
            _LiveMarketCard(snapshot: liveSnapshot),
            const SizedBox(height: 8),
            _LiveExecutionCheck(aiSide: side, snapshot: liveSnapshot),
            const SizedBox(height: 16),
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
            const SizedBox(height: 15),
            _Heading('DAY TRADING PLAN', txt(data['strategy_mode'], 'DAY_TRADING')),
            const SizedBox(height: 9),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: panel,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: tradePlan.isNotEmpty ? accent.withValues(alpha: .4) : line),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('ALUR ANALISIS', style: TextStyle(color: muted, fontSize: 9, letterSpacing: 1.2)),
                const SizedBox(height: 9),
                const Wrap(spacing: 7, runSpacing: 7, children: [
                  _Tag('H4 • ARAH BESAR'), _Tag('H1 • BIAS'), _Tag('M15 • SETUP'), _Tag('M5 • TRIGGER'),
                ]),
                const SizedBox(height: 12),
                if (tradePlan.isEmpty)
                  const Text('Belum ada rencana entry valid. Tunggu konfirmasi H4 + H1 + M15 + order flow.',
                    style: TextStyle(color: muted, fontSize: 11, height: 1.4))
                else ...[
                  Row(children: [
                    Expanded(child: _PlanValue('ENTRY', tradePlan['entry'])),
                    Expanded(child: _PlanValue('STOP LOSS', tradePlan['stop_loss'])),
                    Expanded(child: _PlanValue('TAKE PROFIT', tradePlan['take_profit'])),
                  ]),
                  const SizedBox(height: 8),
                  Text('Risk/Reward: 1:${txt(tradePlan['risk_reward'], '2.0')} • Acuan M15',
                    style: const TextStyle(color: muted, fontSize: 10)),
                ],
              ]),
            ),
            const SizedBox(height: 15),
            const _Heading('MULTI-COIN SCANNER', 'Pemindaian setup pada daftar aset yang dipilih'),
            const SizedBox(height: 9),
            _Scanner(future: scanner, selectedSymbol: selectedSymbol, onSelect: onSymbolChanged),
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
            const _Heading('BACKTEST & PERFORMANCE', 'Evaluasi historis dengan biaya transaksi dan data out-of-sample'),
            const SizedBox(height: 9),
            _BacktestCard(future: backtest),
            const SizedBox(height: 15),
            const _Heading('SIGNAL CENTER', 'Riwayat sinyal dan status yang tersimpan di backend'),
            const SizedBox(height: 9),
            _SignalPerformance(future: signalPerformance),
            const SizedBox(height: 9),
            _SignalCenter(future: signals),
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


class _LiveMarketCard extends StatelessWidget {
  const _LiveMarketCard({required this.snapshot});
  final BinanceLiveSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final price = snapshot.lastPrice;
    final change = snapshot.changePercent;
    final imbalance = snapshot.orderBookImbalance;
    final priceText = price == null
        ? 'Menunggu data...'
        : price.toStringAsFixed(price >= 100 ? 2 : 5);
    final changeText = change == null
        ? '—'
        : '${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%';
    final flow = snapshot.tradeSide ?? '—';
    final flowColor = flow == 'BUY' ? green : flow == 'SELL' ? red : muted;
    final imbalanceText = imbalance == null
        ? '—'
        : '${imbalance >= 0 ? '+' : ''}${imbalance.toStringAsFixed(1)}%';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.circle, size: 8,
                  color: snapshot.connected ? green : red),
              const SizedBox(width: 6),
              Text(snapshot.connected ? 'BINANCE WEBSOCKET LIVE' : 'WEBSOCKET RECONNECTING',
                  style: TextStyle(color: snapshot.connected ? green : red,
                      fontSize: 9, fontWeight: FontWeight.w900, letterSpacing: .7)),
              const Spacer(),
              Text('PUBLIC STREAM • NO API KEY',
                  style: TextStyle(color: muted, fontSize: 7)),
            ]),
            const SizedBox(height: 12),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('LIVE PRICE', style: TextStyle(color: muted, fontSize: 8)),
                const SizedBox(height: 3),
                Text(priceText, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900)),
              ])),
              Text(changeText, style: TextStyle(
                  color: change == null ? muted : change >= 0 ? green : red,
                  fontSize: 13, fontWeight: FontWeight.w800)),
            ]),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(child: _LiveMetric(label: 'LAST AGGRESSOR', value: flow, color: flowColor)),
              Expanded(child: _LiveMetric(label: 'BOOK IMBALANCE', value: imbalanceText,
                  color: imbalance == null ? muted : imbalance >= 0 ? green : red)),
              Expanded(child: _LiveMetric(label: '24H QUOTE VOL', value:
                  snapshot.quoteVolume == null ? '—' : snapshot.quoteVolume!.toStringAsFixed(0))),
            ]),
            if (snapshot.updatedAt != null) ...[
              const SizedBox(height: 7),
              Text('Update: ${snapshot.updatedAt!.toLocal().toString().substring(11, 19)}',
                  style: const TextStyle(color: muted, fontSize: 8)),
            ],
          ],
        ),
      ),
    );
  }
}

class _LiveExecutionCheck extends StatelessWidget {
  const _LiveExecutionCheck({required this.aiSide, required this.snapshot});
  final String aiSide;
  final BinanceLiveSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final imbalance = snapshot.orderBookImbalance;
    final delta = snapshot.buyAggressorVolume - snapshot.sellAggressorVolume;
    final tradeTime = snapshot.lastTradeAt;
    final tradeFresh = tradeTime != null &&
        DateTime.now().difference(tradeTime).inSeconds <= 15;
    final hasLiveInputs = snapshot.connected && imbalance != null && tradeFresh;
    final confirmed = hasLiveInputs &&
        ((aiSide == 'BUY' && delta > 0 && imbalance >= 5) ||
         (aiSide == 'SELL' && delta < 0 && imbalance <= -5));
    final waiting = aiSide == 'BUY' || aiSide == 'SELL';
    final title = !waiting
        ? 'BELUM ADA SETUP AI'
        : !hasLiveInputs
            ? 'MENUNGGU KONFIRMASI LIVE'
            : confirmed
                ? 'LIVE FLOW SEARAH DENGAN AI'
                : 'LIVE FLOW BELUM MENDUKUNG';
    final color = confirmed ? green : waiting ? blue : muted;
    final deltaText = delta >= 0 ? '+${delta.toStringAsFixed(3)}' : delta.toStringAsFixed(3);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('LIVE EXECUTION CHECK',
              style: TextStyle(color: muted, fontSize: 9, letterSpacing: .8)),
          const SizedBox(height: 7),
          Row(children: [
            Icon(Icons.bolt_rounded, color: color, size: 16),
            const SizedBox(width: 7),
            Expanded(child: Text(title,
                style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w900))),
          ]),
          const SizedBox(height: 6),
          Text('Taker delta sesi: $deltaText • Book imbalance: ${imbalance == null ? '—' : imbalance.toStringAsFixed(1) + '%'}',
              style: const TextStyle(color: muted, fontSize: 8)),
          const SizedBox(height: 4),
          const Text('Pemeriksaan tambahan dari stream sejak koneksi aktif; tidak mengubah sinyal tersimpan dan bukan instruksi entry otomatis.',
              style: TextStyle(color: muted, fontSize: 8, height: 1.35)),
        ]),
      ),
    );
  }
}

class _LiveMetric extends StatelessWidget {
  const _LiveMetric({required this.label, required this.value, this.color = Colors.white});
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: muted, fontSize: 7)),
      const SizedBox(height: 3),
      Text(value, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w800)),
    ],
  );
}

class _Scanner extends StatelessWidget {
  const _Scanner({required this.future, required this.selectedSymbol, required this.onSelect});
  final Future<List<Map<String, dynamic>>> future;
  final String selectedSymbol;
  final ValueChanged<String?> onSelect;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(10),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting && !snap.hasData) {
            return const Padding(
              padding: EdgeInsets.all(12),
              child: Center(child: LinearProgressIndicator(minHeight: 2)),
            );
          }
          if (snap.hasError) {
            return Text('Scanner tidak tersedia: ${snap.error}',
              style: const TextStyle(color: muted, fontSize: 9));
          }
          final items = snap.data ?? [];
          if (items.isEmpty) return const Text('Belum ada hasil pemindaian.',
            style: TextStyle(color: muted, fontSize: 9));
          return Column(
            children: items.map((item) {
              final symbol = txt(item['symbol'], '--');
              final side = txt(item['side'], 'UNAVAILABLE').toUpperCase();
              final available = item['scanner_status'] == 'OK';
              final color = side == 'BUY' ? green : side == 'SELL' ? red : blue;
              final selected = symbol == selectedSymbol;
              return InkWell(
                onTap: available ? () => onSelect(symbol) : null,
                borderRadius: BorderRadius.circular(10),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 10),
                  decoration: BoxDecoration(
                    color: selected ? soft : Colors.transparent,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(children: [
                    Expanded(child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(symbol, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w900)),
                        const SizedBox(height: 3),
                        Text(available
                          ? '${number(item['confluence_score'])}/${number(item['max_confluence'])} confluence'
                          : 'Data tidak tersedia',
                          style: const TextStyle(color: muted, fontSize: 8)),
                      ],
                    )),
                    if (available)
                      Text(side, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w900))
                    else
                      const Icon(Icons.error_outline, color: muted, size: 15),
                    const SizedBox(width: 7),
                    const Icon(Icons.chevron_right, color: muted, size: 16),
                  ]),
                ),
              );
            }).toList(),
          );
        },
      ),
    ),
  );
}


class _CandlestickChart extends StatelessWidget {
  const _CandlestickChart({required this.future, required this.interval, required this.onIntervalChanged});
  final Future<List<Map<String, dynamic>>> future;
  final String interval;
  final ValueChanged<String> onIntervalChanged;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting && !snap.hasData) {
            return const SizedBox(height: 190, child: Center(child: CircularProgressIndicator(strokeWidth: 2)));
          }
          final rows = snap.data ?? [];
          if (snap.hasError || rows.length < 3) {
            return SizedBox(height: 190, child: Center(child: Text(
              snap.hasError ? 'Candlestick belum tersedia: ${snap.error}' : 'Data candle belum cukup.',
              textAlign: TextAlign.center, style: const TextStyle(color: muted, fontSize: 9))));
          }
          final last = rows.last;
          final firstClose = doubleVal(rows.first['close']);
          final lastClose = doubleVal(last['close']);
          final change = firstClose == 0 ? 0.0 : (lastClose - firstClose) / firstClose * 100;
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Text('CANDLESTICK', style: TextStyle(color: muted, fontSize: 9, fontWeight: FontWeight.bold)),
              const Spacer(),
              DropdownButton<String>(
                value: interval,
                isDense: true,
                underline: const SizedBox.shrink(),
                dropdownColor: panel,
                style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                items: ['5m', '15m', '1h', '4h'].map((v) => DropdownMenuItem(value: v, child: Text(v.toUpperCase()))).toList(),
                onChanged: (value) { if (value != null) onIntervalChanged(value); },
              ),
              const SizedBox(width: 8),
              Text(price(last['close']), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900)),
              const SizedBox(width: 8),
              Text('${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
                style: TextStyle(color: change >= 0 ? green : red, fontSize: 9, fontWeight: FontWeight.bold)),
            ]),
            const SizedBox(height: 8),
            SizedBox(height: 175, width: double.infinity,
              child: CustomPaint(painter: _CandlePainter(rows))),
            const SizedBox(height: 5),
            Row(children: [
              const Text('80 candle terakhir • ${interval.toUpperCase()}', style: TextStyle(color: muted, fontSize: 8)),
              const Spacer(),
              Text('Sumber: Binance Spot', style: const TextStyle(color: muted, fontSize: 8)),
            ]),
          ]);
        },
      ),
    ),
  );
}

class _CandlePainter extends CustomPainter {
  _CandlePainter(this.rows);
  final List<Map<String, dynamic>> rows;

  @override
  void paint(Canvas canvas, Size size) {
    if (rows.isEmpty || size.width <= 0 || size.height <= 0) return;
    final values = rows.map((r) => [
      doubleVal(r['high']), doubleVal(r['low']), doubleVal(r['open']), doubleVal(r['close'])
    ]).toList();
    final minPrice = values.map((v) => v[1]).reduce(math.min);
    final maxPrice = values.map((v) => v[0]).reduce(math.max);
    final span = (maxPrice - minPrice).abs();
    if (span == 0) return;
    final padTop = 7.0, padBottom = 7.0;
    final chartHeight = size.height - padTop - padBottom;
    double y(double p) => padTop + (maxPrice - p) / span * chartHeight;
    final grid = Paint()..color = line.withValues(alpha: .65)..strokeWidth = .6;
    for (var i = 0; i < 4; i++) {
      final gy = padTop + chartHeight * i / 3;
      canvas.drawLine(Offset(0, gy), Offset(size.width, gy), grid);
    }
    final step = size.width / rows.length;
    final bodyWidth = math.max(2.0, step * .58);
    final wickPaint = Paint()..strokeWidth = 1.0;
    for (var i = 0; i < values.length; i++) {
      final v = values[i];
      final rising = v[3] >= v[2];
      final color = rising ? green : red;
      final x = step * (i + .5);
      wickPaint.color = color;
      canvas.drawLine(Offset(x, y(v[0])), Offset(x, y(v[1])), wickPaint);
      final top = math.min(y(v[2]), y(v[3]));
      final bottom = math.max(y(v[2]), y(v[3]));
      final body = Rect.fromLTRB(x - bodyWidth / 2, top, x + bodyWidth / 2,
        math.max(top + 1.2, bottom));
      canvas.drawRect(body, Paint()..color = color);
    }
    final last = values.last[3];
    final currentY = y(last);
    final currentLine = Paint()..color = blue.withValues(alpha: .8)..strokeWidth = .8;
    canvas.drawLine(Offset(0, currentY), Offset(size.width, currentY), currentLine);
  }

  @override
  bool shouldRepaint(covariant _CandlePainter oldDelegate) => oldDelegate.rows != rows;
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



class _BacktestCard extends StatelessWidget {
  const _BacktestCard({required this.future});
  final Future<Map<String, dynamic>> future;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting && !snap.hasData) {
            return const SizedBox(height: 2, child: LinearProgressIndicator());
          }
          if (snap.hasError) {
            return Text('Backtest belum tersedia: ${snap.error}',
              style: const TextStyle(color: muted, fontSize: 9));
          }
          final data = snap.data ?? {};
          final overall = mapVal(data['overall']);
          final out = mapVal(data['out_of_sample']);
          if (overall.isEmpty) return const Text('Belum ada hasil backtest.',
            style: TextStyle(color: muted, fontSize: 9));
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text('${txt(data['symbol'], '--')} • ${txt(data['timeframe'], '--').toUpperCase()}',
                style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w900))),
              Text('${number(data['candles'])} candles',
                style: const TextStyle(color: muted, fontSize: 8)),
            ]),
            const SizedBox(height: 10),
            const Text('OUT-OF-SAMPLE', style: TextStyle(color: blue, fontSize: 8, fontWeight: FontWeight.w900)),
            const SizedBox(height: 8),
            Row(children: [
              _Metric(label: 'WIN RATE', value: '${decimal(out['win_rate_pct'])}%'),
              _Metric(label: 'TRADES', value: txt(out['trades'], '0')),
              _Metric(label: 'PROFIT FACTOR', value: out['profit_factor'] == null ? 'N/A' : decimal(out['profit_factor'])),
              _Metric(label: 'MAX DD', value: '${decimal(out['max_drawdown_pct'])}%'),
            ]),
            const SizedBox(height: 10),
            Row(children: [
              _Metric(label: 'OVERALL RETURN', value: '${decimal(overall['total_return_pct'])}%'),
              _Metric(label: 'EXPECTANCY', value: '${decimal(overall['expectancy_pct'])}%'),
              _Metric(label: 'SIGNALS', value: txt(data['signal_count'], '0')),
              _Metric(label: 'NO TRADE', value: txt(data['no_trade_count'], '0')),
            ]),
            const SizedBox(height: 9),
            Text('Strategi: ${txt(data['strategy'], 'AI intelligence')} • Hasil historis bukan jaminan performa live.',
              style: const TextStyle(color: muted, fontSize: 8, height: 1.4)),
            if (strings(data['limitations']).isNotEmpty)
              Text(strings(data['limitations']).first,
                style: const TextStyle(color: muted, fontSize: 8, height: 1.4)),
          ]);
        },
      ),
    ),
  );
}

class _SignalPerformance extends StatelessWidget {
  const _SignalPerformance({required this.future});
  final Future<Map<String, dynamic>> future;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting && !snap.hasData) {
            return const SizedBox(height: 2);
          }
          final data = snap.data ?? <String, dynamic>{};
          if (data.isEmpty || data['unavailable_reason'] != null) {
            return Text(
              'Statistik sinyal belum tersedia.',
              style: TextStyle(color: muted, fontSize: 9),
            );
          }
          final wr = data['win_rate_pct'];
          final winRateLabel = wr == null ? 'N/A' : '${wr}%';
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                _Metric(label: 'WIN RATE LIVE', value: winRateLabel),
                _Metric(label: 'TP / WIN', value: txt(data['wins'], '0')),
                _Metric(label: 'SL / LOSS', value: txt(data['losses'], '0')),
                _Metric(label: 'ACTIVE', value: txt(data['active'], '0')),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                _Metric(label: 'TOTAL SIGNAL', value: txt(data['total_signals'], '0')),
                _Metric(label: 'CLOSED', value: txt(data['completed'], '0')),
                _Metric(label: 'AMBIGUOUS', value: txt(data['ambiguous'], '0')),
                _Metric(label: 'NET R', value: txt(data['total_realized_r'], '0')),
              ]),
              const SizedBox(height: 7),
              Text(
                txt(data['method_note'], ''),
                style: const TextStyle(color: muted, fontSize: 8, height: 1.4),
              ),
            ],
          );
        },
      ),
    ),
  );
}

class _SignalCenter extends StatelessWidget {
  const _SignalCenter({required this.future});
  final Future<List<Map<String, dynamic>>> future;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(10),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting && !snap.hasData) {
            return const SizedBox(height: 2);
          }
          if (snap.hasError) {
            return Text('Riwayat sinyal belum tersedia: ${snap.error}',
              style: TextStyle(color: muted, fontSize: 9));
          }
          final items = snap.data ?? [];
          if (items.isEmpty) return Text('Belum ada riwayat sinyal tersimpan.',
            style: TextStyle(color: muted, fontSize: 9));
          return Column(children: items.take(12).map((item) {
            final side = item['side'] ?? 'UNKNOWN';
            final status = item['status'] ?? 'UNKNOWN';
            final color = side == 'BUY' ? green : side == 'SELL' ? red : muted;
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Container(width: 7, height: 7, margin: const EdgeInsets.only(top: 4),
                  decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                const SizedBox(width: 9),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${txt(item['symbol'], '--')} • $side',
                    style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w900)),
                  const SizedBox(height: 3),
                  Text('${txt(item['timeframe_set'], '--')} • $status • ${txt(item['outcome'], 'OPEN')}',
                    style: TextStyle(color: muted, fontSize: 8)),
                  if (item['entry'] != null) Text('Entry ${price(item['entry'])} • SL ${price(item['stop_loss'])} • TP ${price(item['take_profit'])}',
                    style: TextStyle(color: muted, fontSize: 8)),
                  if (strings(item['reasons']).isNotEmpty)
                    Text(strings(item['reasons']).take(2).join(' '),
                      maxLines: 2, overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: muted, fontSize: 8)),
                ])),
              ]),
            );
          }).toList());
        },
      ),
    ),
  );
}

class _Inbox extends StatelessWidget {
  const _Inbox({required this.future, required this.markRead});
  final Future<List<Map<String, dynamic>>> future;
  final Future<void> Function(int) markRead;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(10),
    child: FutureBuilder<List<Map<String, dynamic>>>(future: future, builder: (context, snap) {
      if (snap.connectionState == ConnectionState.waiting) return const SizedBox(height: 2);
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
