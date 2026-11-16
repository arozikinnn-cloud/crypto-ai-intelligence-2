import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb, TargetPlatform;

/// Public Firebase client configuration for Crypto AI Intelligence V7.
/// Never place Firebase service-account credentials in this file.
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) throw UnsupportedError('Firebase web is not configured.');
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      default:
        throw UnsupportedError('Firebase is configured for Android only.');
    }
  }

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyBNTxcCcnktIfp9IlV5N9C3QttBGB6lkUQ',
    appId: '1:1089889703969:android:0d355dd66690cef96e6b60',
    messagingSenderId: '1089889703969',
    projectId: 'crypto-ai-intelligence-v7',
    storageBucket: 'crypto-ai-intelligence-v7.firebasestorage.app',
  );
}
