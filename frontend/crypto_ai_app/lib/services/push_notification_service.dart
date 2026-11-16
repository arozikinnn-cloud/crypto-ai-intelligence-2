import 'package:firebase_messaging/firebase_messaging.dart';

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Notification payloads are displayed by Android when the app is backgrounded.
  // Data-only message handling will be added with the backend sender integration.
}

class PushNotificationService {
  static Future<void> initialize() async {
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission(alert: true, badge: true, sound: true);
    // Fetch the device token; backend registration is a separate pending step.
    await messaging.getToken();
    messaging.onTokenRefresh.listen((token) {
      // Connect token refresh to the backend registration endpoint in the next phase.
    });
  }
}
