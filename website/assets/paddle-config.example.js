// Paddle client-side configuration.
//
// Copy this file to `paddle-config.js` on the server (NOT committed to git):
//
//   sudo -u jyry cp website/assets/paddle-config.example.js \
//                   website/assets/paddle-config.js
//   sudo -u jyry nano website/assets/paddle-config.js
//
// Then fill in the real values below and run rsync to /var/www/jyry.
//
// The token is PUBLIC by design — Paddle's server validates that it matches
// the transaction's seller — so it is safe to ship in the page source. We
// keep it out of git only so `git pull` doesn't keep wiping it.
//
// Token shapes:
//   sandbox: test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
//   live:    live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
//
// Create one at: Paddle Dashboard → Developer Tools → Authentication
// → "Client-side tokens" → New token.

window.PADDLE_CLIENT_TOKEN = "REPLACE_ME";
window.PADDLE_ENVIRONMENT = "sandbox"; // or "production"
