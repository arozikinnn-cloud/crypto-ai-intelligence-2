import 'dart:convert';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:http/http.dart' as http;

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // FCM notification payloads are rendered by Android while the app is backgrounded.
}

class PushNotificationService {
  static const _apiBase = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://crypto-ai-intelligence-2-backend.vercel.app/api/v1',
  );

  static Future<void> initialize() async {
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    final messaging = FirebaseMessaging.instance;
    final settings = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      return;
    }

    final token = await messaging.getToken();
    if (token != null && token.isNotEmpty) {
      await _registerToken(token);
    }

    messaging.onTokenRefresh.listen((token) async {
      await _registerToken(token);
    });
  }

  static Future<void> _registerToken(String token) async {
    final base = _apiBase.replaceFirst(RegExp(r'/+$'), '');
    try {
      final response = await http
          .post(
            Uri.parse('$base/devices/fcm-token'),
            headers: const {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: jsonEncode({'token': token, 'platform': 'android'}),
          )
          .timeout(const Duration(seconds: 15));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        // Token registration will retry on the next app start or token refresh.
      }
    } catch (_) {
      // Keep app startup resilient when the phone is offline or backend is unavailable.
    }
  }
}
