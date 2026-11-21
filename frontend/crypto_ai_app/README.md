# Flutter client

The Flutter client reads the combined market-intelligence API; it does not place exchange orders.

## Run locally

1. Start the backend API.
2. From this directory run `flutter pub get`.
3. Run on an Android emulator with:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

For a physical Android phone, set `API_BASE_URL` to the backend machine's reachable LAN address, for example `http://192.168.1.10:8000/api/v1`. Use HTTPS for any internet-facing deployment. Do not embed API secrets in the app.

The dashboard requests `GET /analysis/intelligence` and renders the decision, confluence score, reasons, and context notes. Loading, API-error, and retry states are included. The Android platform folder/build configuration must still be generated and verified with the Flutter SDK before producing an APK.

## CI

The Mobile CI workflow runs dependency resolution, Dart formatting, static analysis, Flutter tests, builds a debug APK, installs and launches it in an Android emulator, and builds ABI-split release APKs. The workflow uploads APK artifacts for 7 days. A CI build is not a substitute for testing push delivery on a physical phone or configuring the persistent TradingAgents worker.
