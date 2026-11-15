import 'package:flutter/material.dart';

import 'services/analysis_api.dart';

void main() => runApp(const CryptoAIApp());

class CryptoAIApp extends StatelessWidget {
  const CryptoAIApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Crypto AI Intelligence',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF087E75)),
          useMaterial3: true,
        ),
        home: const DashboardShell(),
      );
}

class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key, this.loadAnalysis});

  final Future<Map<String, dynamic>> Function()? loadAnalysis;

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  late Future<Map<String, dynamic>> _analysis;

  @override
  void initState() {
    super.initState();
    _analysis = _load();
  }

  Future<Map<String, dynamic>> _load() =>
      widget.loadAnalysis?.call() ?? AnalysisApi().fetchIntelligence();

  void _refresh() {
    setState(() => _analysis = _load());
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Crypto AI Intelligence'),
          actions: [
            IconButton(
              tooltip: 'Refresh analysis',
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: FutureBuilder<Map<String, dynamic>>(
          future: _analysis,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _MessageState(
                icon: Icons.cloud_off_outlined,
                title: 'Market data unavailable',
                message: snapshot.error.toString(),
                action: FilledButton.icon(
                  onPressed: _refresh,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try again'),
                ),
              );
            }
            final data = snapshot.data;
            if (data == null) {
              return const _MessageState(
                icon: Icons.info_outline,
                title: 'No analysis available',
                message: 'The API returned an empty response.',
              );
            }
            return _AnalysisView(data: data);
          },
        ),
      );
}

class _AnalysisView extends StatelessWidget {
  const _AnalysisView({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final reasons = _strings(data['reasons']);
    final notes = _strings(data['context_notes']);
    final side = data['side']?.toString() ?? 'UNKNOWN';
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(data['symbol']?.toString() ?? 'UNKNOWN',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text(side,
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        )),
                const SizedBox(height: 8),
                Text('Confluence: ${data['confluence_score'] ?? '-'} / '
                    '${data['max_confluence'] ?? '-'}'),
                Text(data['score_note']?.toString() ??
                    'Decision based on available market evidence.'),
              ],
            ),
          ),
        ),
        _SectionCard(
          title: 'Analysis reasons',
          items: reasons,
          emptyMessage: 'No reasons supplied by the analysis engine.',
        ),
        _SectionCard(
          title: 'Market context',
          items: notes,
          emptyMessage: 'No additional context available.',
        ),
        const Padding(
          padding: EdgeInsets.all(8),
          child: Text(
            'Decision support only. This app does not place trades. '
            'Verify data availability and manage risk independently.',
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }

  List<String> _strings(dynamic value) => value is List
      ? value.map((item) => item.toString()).toList()
      : const [];
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.title,
    required this.items,
    required this.emptyMessage,
  });

  final String title;
  final List<String> items;
  final String emptyMessage;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              if (items.isEmpty)
                Text(emptyMessage)
              else
                ...items.map((item) => ListTile(
                      dense: true,
                      leading: const Icon(Icons.info_outline),
                      title: Text(item),
                    )),
            ],
          ),
        ),
      );
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 48),
              const SizedBox(height: 12),
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(message, textAlign: TextAlign.center),
              if (action != null) ...[
                const SizedBox(height: 16),
                action!,
              ],
            ],
          ),
        ),
      );
}
