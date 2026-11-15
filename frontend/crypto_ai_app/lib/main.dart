import 'package:flutter/material.dart';

void main() => runApp(const CryptoAIApp());

class CryptoAIApp extends StatelessWidget {
  const CryptoAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Crypto AI Intelligence',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
      home: const DashboardShell(),
    );
  }
}

class DashboardShell extends StatelessWidget {
  const DashboardShell({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Crypto AI Intelligence')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: const [
          Card(
            child: ListTile(
              leading: Icon(Icons.monitor_heart_outlined),
              title: Text('System foundation'),
              subtitle: Text('Application shell is running. Market analysis is not connected yet.'),
            ),
          ),
          Card(
            child: ListTile(
              leading: Icon(Icons.insights_outlined),
              title: Text('Market intelligence'),
              subtitle: Text('Market data and signal engine are planned for later phases.'),
            ),
          ),
          Card(
            child: ListTile(
              leading: Icon(Icons.notifications_outlined),
              title: Text('Notifications'),
              subtitle: Text('Notification delivery will be implemented in a later phase.'),
            ),
          ),
        ],
      ),
    );
  }
}
