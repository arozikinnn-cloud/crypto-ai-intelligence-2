# Deploy backend for Android (free-tier starter)

This repository includes a Render Blueprint at the repository root. It deploys
the FastAPI backend as a public HTTPS API so an Android phone can reach it
without a computer.

## Important free-tier limitations

- Render Free web services sleep after 15 minutes without inbound traffic.
  The first request after sleep can take about a minute to wake the service.
- The free service has an ephemeral filesystem. Do not use its local SQLite
  database for data that must survive restarts/redeploys.
- Supabase Free Postgres currently includes 500 MB, but projects can pause
  after a week of low activity. Check the provider's current terms.
- This setup is for testing/hobby use, not reliable always-on trading alerts.
  Render's sleep means Binance collectors stop while the API is asleep. The
  Android app's foreground polling can wake the API, but it cannot guarantee
  continuous collection or alerts while the app is closed.
- Do not add payment details or upgrade plans unless you have reviewed the
  price and explicitly chosen to do so.

## Setup

1. Create a Supabase project on its Free plan.
2. In Supabase, open Project Settings -> Database and copy the connection
   string. Use the direct connection string if available. Keep the password
   private; never commit it to GitHub or send it in chat.
3. In Render, choose New -> Blueprint and connect this repository.
   Render will detect the root render.yaml.
4. During service setup, set DATABASE_URL to the Supabase connection string.
   Render stores it as a secret environment variable.
5. Wait for deployment. Test the root URL and /api/v1/health/ready.
6. Copy the base API URL in this exact format:
   https://YOUR-SERVICE.onrender.com/api/v1
7. In GitHub, open Settings -> Secrets and variables -> Actions -> Variables.
   Create repository variable API_BASE_URL with that URL.
8. Run Actions -> Mobile CI -> Run workflow. The APK will be uploaded as the
   crypto-ai-intelligence-debug-apk artifact if Flutter checks and build pass.
9. Download the APK artifact from the successful workflow run and install it
   on Android. Android may ask permission to install apps from that source.

## Troubleshooting

- If /api/v1/health/ready fails, check Render logs and DATABASE_URL.
- If the app says API URL is missing, confirm API_BASE_URL was set before
  running Mobile CI.
- If the app times out on the first request, wait for Render to wake, then
  tap refresh.
- Never publish the Supabase database password or use a local LAN address
  such as 192.168.x.x or emulator-only 10.0.2.2 in the APK.
