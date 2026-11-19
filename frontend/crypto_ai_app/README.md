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

The Mobile CI workflow runs dependency resolution, Dart formatting, static analysis, and widget tests. It does not yet certify a signed Android release APK.


## Live liquidation context
- The mobile dashboard subscribes to Binance USDⓈ-M Futures `<symbol>@forceOrder` for the currently selected symbol using the public WebSocket endpoint `wss://fstream.binance.com/market/ws/{symbol}@forceOrder`.
- The stream is read-only and does not require an API key. It is separate from the Spot market data used by the existing candle/market dashboard.
- Binance publishes a liquidation snapshot at most once per symbol per 1000 ms; it does not send a message when no liquidation occurs. Treat this as a live event feed, not a complete historical liquidation tape or liquidation heatmap.
- The app retains up to 20 received events in memory for the current session only. Events missed while the app is paused/offline are not backfilled.
- SELL force orders generally close long positions and BUY force orders generally close short positions. This is an interpretation of the forced order side, not an entry signal.
- The stream disconnects while the app is paused and reconnects when resumed or when the selected symbol changes. Reconnection uses bounded exponential backoff.
- Android release builds must include `android.permission.INTERNET`; the Mobile CI workflow adds it to the generated main manifest before building.
