import 'dart:async';
import 'dart:convert';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:http/http.dart' as http;

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Android displays FCM notification payloads while the app is backgrounded.
}

class PushNotificationService {
  static const _apiBase = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://crypto-ai-intelligence-2-backend.vercel.app/api/v1',
  );

  static bool _initialized = false;
  static bool _notificationsAllowed = false;
  static bool _registrationSucceeded = false;
  static StreamSubscription<String>? _tokenRefreshSubscription;
  static StreamSubscription<RemoteMessage>? _foregroundMessageSubscription;

  static void Function(String title, String body)? onForegroundNotification;

  static bool get initialized => _initialized;
  static bool get notificationsAllowed => _notificationsAllowed;
  static bool get registrationSucceeded => _registrationSucceeded;

  static Future<void> initialize() async {
    if (_initialized) {
      await refreshRegistration();
      return;
    }

    // Do not let an FCM/network/configuration problem prevent the dashboard
    // from starting. Registration is retried when the app returns to foreground.
    try {
      FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
      _notificationsAllowed =
          settings.authorizationStatus == AuthorizationStatus.authorized ||
          settings.authorizationStatus == AuthorizationStatus.provisional;
      _initialized = true;

      await _foregroundMessageSubscription?.cancel();
      _foregroundMessageSubscription = FirebaseMessaging.onMessage.listen((message) {
        final title = message.notification?.title ??
            message.data['title']?.toString() ??
            'Crypto AI Intelligence';
        final body = message.notification?.body ??
            message.data['body']?.toString() ??
            '';
        onForegroundNotification?.call(title, body);
      });

      if (!_notificationsAllowed) {
        _registrationSucceeded = false;
        return;
      }

      await refreshRegistration();
    } catch (_) {
      // A later app-resume event retries Firebase/token initialization.
      _initialized = false;
    }
  }

  /// Re-fetch and register the current token on app resume. This recovers from
  /// first-run network outages and from the backend being temporarily offline.
  static Future<void> refreshRegistration() async {
    if (!_initialized) return;
    try {
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.getNotificationSettings();
      _notificationsAllowed =
          settings.authorizationStatus == AuthorizationStatus.authorized ||
          settings.authorizationStatus == AuthorizationStatus.provisional;
      if (!_notificationsAllowed) {
        _registrationSucceeded = false;
        await _tokenRefreshSubscription?.cancel();
        _tokenRefreshSubscription = null;
        return;
      }

      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) {
        await _registerToken(token);
      }
      _tokenRefreshSubscription ??= messaging.onTokenRefresh.listen((token) {
        unawaited(_registerToken(token));
      });
    } catch (_) {
      // Keep app lifecycle and dashboard refresh independent from FCM.
    }
  }

  static Future<bool> _registerToken(String token) async {
    final base = _apiBase.replaceFirst(RegExp(r'/+$'), '');
    try {
      final response = await http
          .post(
            Uri.parse('$base/devices/fcm-token'),
            headers: const {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            body: jsonEncode({'token': token, 'platform': 'android'}),
          )
          .timeout(const Duration(seconds: 15));
      _registrationSucceeded =
          response.statusCode >= 200 && response.statusCode < 300;
      return _registrationSucceeded;
    } catch (_) {
      // No token is logged or exposed; retry at the next app start/resume.
      _registrationSucceeded = false;
      return false;
    }
  }
}
