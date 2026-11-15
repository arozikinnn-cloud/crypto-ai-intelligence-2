import 'dart:async';

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
  const DashboardShell({
    super.key,
    this.loadAnalysis,
    this.loadNotifications,
  });

  final Future<Map<String, dynamic>> Function()? loadAnalysis;
  final Future<List<Map<String, dynamic>>> Function()? loadNotifications;

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell>
    with WidgetsBindingObserver {
  final AnalysisApi _api = AnalysisApi();
  late Future<Map<String, dynamic>> _analysis;
  late Future<List<Map<String, dynamic>>> _notifications;
  Timer? _notificationPoller;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _analysis = _load();
    _notifications = _loadNotifications();
    _startNotificationPolling();
  }

  Future<Map<String, dynamic>> _load() =>
      widget.loadAnalysis?.call() ?? _api.fetchIntelligence();

  Future<List<Map<String, dynamic>>> _loadNotifications() =>
      widget.loadNotifications?.call() ?? _api.fetchNotifications();

  void _startNotificationPolling() {
    _notificationPoller?.cancel();
    _notificationPoller = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!mounted) return;
      setState(() => _notifications = _loadNotifications());
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (mounted) setState(() => _notifications = _loadNotifications());
      _startNotificationPolling();
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _notificationPoller?.cancel();
      _notificationPoller = null;
    }
  }

  Future<void> _markNotificationRead(int id) async {
    await _api.markNotificationRead(id);
    if (mounted) setState(() => _notifications = _loadNotifications());
  }

  void _refresh() {
    setState(() {
      _analysis = _load();
      _notifications = _loadNotifications();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _notificationPoller?.cancel();
    _api.close();
    super.dispose();
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
            return _AnalysisView(
              data: data,
              notifications: _notifications,
              onMarkNotificationRead: _markNotificationRead,
            );
          },
        ),
      );
}

class _AnalysisView extends StatelessWidget {
  const _AnalysisView({
    required this.data,
    required this.notifications,
    required this.onMarkNotificationRead,
  });

  final Map<String, dynamic> data;
  final Future<List<Map<String, dynamic>>> notifications;
  final Future<void> Function(int id) onMarkNotificationRead;

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
        _NotificationInbox(
          notifications: notifications,
          onMarkRead: onMarkNotificationRead,
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

class _NotificationInbox extends StatelessWidget {
  const _NotificationInbox({
    required this.notifications,
    required this.onMarkRead,
  });

  final Future<List<Map<String, dynamic>>> notifications;
  final Future<void> Function(int id) onMarkRead;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Signal notification inbox',
                  style: Theme.of(context).textTheme.titleMedium),
              FutureBuilder<List<Map<String, dynamic>>>(
                future: notifications,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Padding(
                      padding: EdgeInsets.all(12),
                      child: LinearProgressIndicator(),
                    );
                  }
                  if (snapshot.hasError) {
                    return Text('Inbox unavailable: ${snapshot.error}');
                  }
                  final items = snapshot.data ?? const [];
                  if (items.isEmpty) return const Text('No notifications yet.');
                  return Column(
                    children: items.map((item) {
                      final id = item['id'] as int?;
                      final read = item['read'] == true;
                      return ListTile(
                        dense: true,
                        title: Text(item['title']?.toString() ?? 'Signal alert'),
                        subtitle: Text(item['message']?.toString() ?? ''),
                        trailing: read
                            ? const Icon(Icons.done, semanticLabel: 'Read')
                            : IconButton(
                                tooltip: 'Mark as read',
                                icon: const Icon(Icons.mark_email_read_outlined),
                                onPressed: id == null
                                    ? null
                                    : () => onMarkRead(id),
                              ),
                      );
                    }).toList(),
                  );
                },
              ),
            ],
          ),
        ),
      );
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
