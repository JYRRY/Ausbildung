# Web Dashboard — Deployment Steps

Adds the Next.js dashboard and FastAPI backend to an existing Hetzner box
that's already running `jyry-bot.service` and `jyry-webhook.service`.
Domain stays the same: `bot.jyrygroup.com`.

## 0. Prerequisites

- Existing `/opt/jyry` checkout, `.venv`, Postgres, Redis (already there
  from the original deployment — see `RUNBOOK.md`).
- Node.js 20+ installed on the box.

```bash
# Add NodeSource if not already installed
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v        # should print v20.x
```

## 1. Pull and install Python deps

```bash
ssh jyry-vm
cd /opt/jyry
sudo -u jyry git pull origin claude/telegram-bot-ausbildung
sudo -u jyry .venv/bin/pip install -e .
sudo -u jyry .venv/bin/alembic upgrade head
```

Migrations 0003-0006 will run; they're backwards-compatible.

## 2. Update `/opt/jyry/.env`

Add these to the existing `.env`:

```bash
# Web dashboard
WEB_PUBLIC_URL=https://bot.jyrygroup.com
WEB_API_PORT=8001
WEB_JWT_SECRET=<openssl rand -base64 48>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
```

In Google Cloud Console, add `https://bot.jyrygroup.com/api/auth/google/callback`
as an authorized redirect URI on the OAuth 2.0 client.

## 3. Build the frontend

```bash
cd /opt/jyry/webapp
sudo -u jyry cp .env.example .env.production
sudo -u jyry vi .env.production
# Set:
#   NEXT_PUBLIC_API_BASE=https://bot.jyrygroup.com
#   INTERNAL_API_BASE=http://127.0.0.1:8001
#   SESSION_COOKIE_NAME=jyry_session

sudo -u jyry npm install --no-audit --no-fund
sudo -u jyry npm run build

# Standalone build needs the static / public assets copied next to it.
sudo -u jyry cp -r .next/static .next/standalone/.next/
sudo -u jyry cp -r public .next/standalone/  2>/dev/null || true
```

## 4. Install the systemd units

```bash
sudo cp /opt/jyry/deploy/systemd/jyry-api.service /etc/systemd/system/
sudo cp /opt/jyry/deploy/systemd/jyry-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jyry-api jyry-web
sudo systemctl status jyry-api jyry-web --no-pager
```

Quick smoke test:

```bash
curl -s http://127.0.0.1:8001/api/health
# → {"ok": true}

curl -s -I http://127.0.0.1:3000/app/signin
# → HTTP/1.1 200 OK
```

## 5. Swap the nginx config

```bash
sudo cp /opt/jyry/deploy/nginx/jyry-bot.jyrygroup.com.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/jyry-bot.jyrygroup.com.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/jyry-webhook.conf
sudo nginx -t && sudo systemctl reload nginx
```

Open `https://bot.jyrygroup.com/app` — you should land on the sign-in page.

## 6. Promote yourself to admin

The first time you sign in via Google, a User row is created with
`is_admin = false`. Promote yourself in psql:

```bash
sudo -u postgres psql jyry -c \
  "UPDATE users SET is_admin = TRUE WHERE email = 'jyrygroup@gmail.com';"
```

Reload the dashboard — the Admin link appears in the sidebar.

## 7. Rollback

Everything bot-only is preserved on `archive/bot-only-v1`:

```bash
sudo systemctl stop jyry-web jyry-api
sudo rm /etc/systemd/system/jyry-{web,api}.service
sudo systemctl daemon-reload
sudo cp /opt/jyry/deploy/nginx/jyry-webhook.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/jyry-webhook.conf /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/jyry-bot.jyrygroup.com.conf
cd /opt/jyry
sudo -u jyry git checkout archive/bot-only-v1
sudo systemctl reload nginx
sudo systemctl restart jyry-bot jyry-webhook
```

Migrations 0006/0005/0004/0003 are additive (downgrades available via
`alembic downgrade -1`) so a partial rollback is also safe.
