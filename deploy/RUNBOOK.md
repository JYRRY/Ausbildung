# JYRY AI — Hetzner Deployment Runbook

Step-by-step guide to bringing JYRY AI online on a fresh Hetzner Cloud VM.
Tested on a CX22 (2 vCPU / 4 GB RAM) running Ubuntu 24.04 LTS — the smallest
plan that comfortably handles the bot, webhook, PostgreSQL and Redis on a
single host.

---

## 0. Provision

Hetzner Cloud → **Add Server**

| Setting       | Value                       |
| ------------- | --------------------------- |
| Location      | Falkenstein or Nuremberg    |
| Image         | Ubuntu 24.04                |
| Type          | CX22 (Shared vCPU)          |
| Networking    | IPv4 + IPv6                 |
| SSH key       | upload your public key      |
| Firewall      | (created in §3 below)       |

Add an **A** record `jyry.example.com → <vm-ipv4>` and an **AAAA** record for
the IPv6. The same hostname serves the marketing site and the Paddle webhook.

---

## 1. Base hardening

SSH in as root and harden the box. The bot doesn't need root after this.

```bash
ssh root@jyry.example.com

# Patches
apt update && apt upgrade -y
apt install -y unattended-upgrades fail2ban
dpkg-reconfigure --priority=low unattended-upgrades

# Non-root deploy user
adduser --disabled-password --gecos "" jyry
usermod -aG sudo jyry
mkdir -p /home/jyry/.ssh
cp /root/.ssh/authorized_keys /home/jyry/.ssh/
chown -R jyry:jyry /home/jyry/.ssh
chmod 700 /home/jyry/.ssh && chmod 600 /home/jyry/.ssh/authorized_keys

# Disable root SSH + password auth
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Reconnect as `jyry` and verify `sudo -i` works before logging out of the root
session.

---

## 2. System dependencies

```bash
sudo apt install -y \
    python3.12 python3.12-venv python3.12-dev \
    postgresql postgresql-contrib \
    redis-server \
    nginx certbot python3-certbot-nginx \
    git build-essential libpq-dev
```

Enable + start the services:

```bash
sudo systemctl enable --now postgresql redis-server nginx
```

---

## 3. Firewall

Hetzner Cloud Firewall (web console) is the cleanest approach. Inbound rules:

| Protocol | Port | Source       | Purpose            |
| -------- | ---- | ------------ | ------------------ |
| TCP      | 22   | your IP only | SSH                |
| TCP      | 80   | 0.0.0.0/0    | HTTP (ACME)        |
| TCP      | 443  | 0.0.0.0/0    | HTTPS (webhook)    |

Outbound: allow all. The bot needs egress to `api.telegram.org`,
`smtp.gmail.com`, `rest.arbeitsagentur.de`, `api.paddle.com` (or `sandbox-api.paddle.com`).

Attach the firewall to the VM. Don't run `ufw` in addition — pick one.

---

## 4. PostgreSQL

```bash
sudo -u postgres psql <<SQL
CREATE USER jyry WITH PASSWORD 'CHANGE_ME_strong_random';
CREATE DATABASE jyry OWNER jyry;
\q
SQL
```

Optional: tighten `pg_hba.conf` to only accept connections from `127.0.0.1`
for the `jyry` user (it's localhost-only by default on Ubuntu).

---

## 5. Application checkout

```bash
sudo mkdir -p /opt/jyry
sudo chown jyry:jyry /opt/jyry
cd /opt/jyry
git clone https://github.com/JYRRY/Ausbildung.git .

python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
```

Generate the Fernet key once and stash it:

```bash
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy `.env.example` → `.env`, fill in:

- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `FERNET_KEY` — the value you just generated
- `DATABASE_URL` — `postgresql+asyncpg://jyry:CHANGE_ME_strong_random@127.0.0.1:5432/jyry`
- `PADDLE_*` — from your Paddle dashboard (see §9 below)
- `WEBHOOK_PUBLIC_URL=https://bot.jyrygroup.com`

Lock the file:

```bash
chmod 600 /opt/jyry/.env
```

---

## 6. Database migrations

```bash
cd /opt/jyry
.venv/bin/alembic upgrade head
```

You should see `INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema`.

Sanity check from `psql`:

```bash
sudo -u postgres psql -d jyry -c "\dt"
# Expect: applications, email_drafts, job_cache, subscriptions,
#         user_specialties, user_states, users, alembic_version
```

---

## 7. systemd units

Copy the unit files and reload:

```bash
sudo cp /opt/jyry/deploy/systemd/jyry-bot.service     /etc/systemd/system/
sudo cp /opt/jyry/deploy/systemd/jyry-webhook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jyry-bot jyry-webhook
```

Verify:

```bash
systemctl status jyry-bot jyry-webhook
journalctl -u jyry-bot -f          # live logs
journalctl -u jyry-webhook -f
```

The bot should print `JYRY AI bot running — Ctrl-C to stop` and the webhook
should bind to `127.0.0.1:8080`.

---

## 8. nginx + TLS for the webhook

The shipped config serves a small marketing site at the root of
`bot.jyrygroup.com` and proxies `/webhook/paddle` to the FastAPI app
on 127.0.0.1:8080. Both share one TLS certificate.

```bash
sudo cp /opt/jyry/deploy/nginx/jyry-webhook.conf /etc/nginx/sites-available/
# If your domain differs, rewrite it:
sudo sed -i 's/bot.jyrygroup.com/<your-domain>/g' \
    /etc/nginx/sites-available/jyry-webhook.conf
sudo ln -s /etc/nginx/sites-available/jyry-webhook.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# TLS
sudo certbot --nginx -d bot.jyrygroup.com
```

Certbot installs a cron renewal automatically. Test with:

```bash
curl -i https://bot.jyrygroup.com/webhook/paddle \
    -H "Content-Type: application/json" \
    -d '{"meta":{"event_name":"ping"}}'
# Expect 200 {"ok":true} (the event is unknown, but the endpoint is reachable).
```

---

## 8.5 Static marketing site

The repo ships a five-page static site under `website/` (home, pricing,
terms, privacy, refund, imprint) used for Paddle merchant verification
and for public product/legal info. nginx serves it from
`/var/www/jyry`.

```bash
# One-time: create the document root.
sudo mkdir -p /var/www/jyry
sudo chown -R www-data:www-data /var/www/jyry

# Every deploy: sync the repo's website/ into the document root.
sudo rsync -av --delete /opt/jyry/website/ /var/www/jyry/
sudo chown -R www-data:www-data /var/www/jyry

# nginx is already serving these paths after §8 above — no reload needed
# unless the config itself changed.
```

Smoke-test the pages:

```bash
for p in / /pricing /terms /privacy /refund /imprint; do
    curl -sI "https://bot.jyrygroup.com$p" | head -n 1
done
# All six should return: HTTP/2 200
```

---

## 9. Paddle wiring

Sandbox and Production are separate accounts with separate dashboards. Do
all of this first against Sandbox (`https://sandbox-vendors.paddle.com`),
verify end-to-end with a test card, then repeat against Production
(`https://vendors.paddle.com`) with the live credentials.

1. **Developer Tools → Authentication → Generate API key**. Copy the value
   (`pdl_…`) into `.env` as `PADDLE_API_KEY`.

2. **Developer Tools → Notifications → Add endpoint**
   - URL: `https://bot.jyrygroup.com/webhook/paddle`
   - Subscribe to: `subscription.created`, `subscription.updated`,
     `subscription.canceled`, `subscription.past_due`, `subscription.paused`,
     `subscription.resumed`.
   - Copy the signing secret (`pdl_ntfset_…`) into `.env` as
     `PADDLE_WEBHOOK_SECRET`.

3. **Catalog → Products** — open each of the three products (JYRY AI Plus,
   Pro, Max) and copy its **price ID** (starts with `pri_…`) into the
   matching env var:
   ```
   PADDLE_PRICE_PLUS=pri_…
   PADDLE_PRICE_PRO=pri_…
   PADDLE_PRICE_MAX=pri_…
   ```

4. Set `PADDLE_API_BASE`:
   - Sandbox: `https://sandbox-api.paddle.com`
   - Production: `https://api.paddle.com`

5. `sudo systemctl restart jyry-bot jyry-webhook` to pick up the new env.

6. Click **Send test event** on the webhook endpoint in the Paddle
   dashboard — `journalctl -u jyry-webhook -f` should log
   `Received Paddle event: …` and return 200.

---

## 10. Operational notes

### Health checks

```bash
systemctl is-active jyry-bot jyry-webhook redis-server postgresql
journalctl -u jyry-bot --since "1 hour ago" | grep -E "ERROR|CRITICAL"
```

### Updating the app

```bash
cd /opt/jyry
sudo -u jyry git pull
sudo -u jyry .venv/bin/pip install -e ".[dev]"
sudo -u jyry .venv/bin/alembic upgrade head
sudo systemctl restart jyry-bot jyry-webhook
```

### Backups

PostgreSQL daily dump (cron `@daily` as user `jyry`):

```bash
0 3 * * * pg_dump -U jyry -h 127.0.0.1 jyry | gzip > /opt/jyry/backups/jyry-$(date +\%F).sql.gz
0 4 * * * find /opt/jyry/backups -name 'jyry-*.sql.gz' -mtime +14 -delete
```

Off-host: pipe through `restic` to a Hetzner Storage Box or an S3-compatible
bucket. Test restoration once a quarter — an untested backup is not a backup.

### Rotating the Fernet key

If the encryption key leaks, every stored Gmail App Password must be
re-encrypted. Procedure (downtime ~2 min):

1. Generate a new key, set it as `FERNET_KEY_NEW` alongside the existing one.
2. Run a one-off script that decrypts each `users.gmail_app_password_enc`
   with the old key and re-encrypts with the new one.
3. Replace `FERNET_KEY` with the new value, drop `FERNET_KEY_NEW`.
4. `sudo systemctl restart jyry-bot jyry-webhook`.

The script is left as a manual exercise — automating it adds risk and the
event should be exceedingly rare.

### Pausing the bot (maintenance)

```bash
sudo systemctl stop jyry-bot
# do work
sudo systemctl start jyry-bot
```

The webhook can stay up; queued events are retried by Paddle.

---

## 11. Troubleshooting

| Symptom                                | First check                                                    |
| -------------------------------------- | -------------------------------------------------------------- |
| `jyry-bot` flapping (start/fail loop)  | `journalctl -u jyry-bot -n 100` — likely missing env var       |
| Webhook 401s                           | `LEMONSQUEEZY_WEBHOOK_SECRET` mismatch, or nginx stripping `X-Signature` |
| `psycopg2 / asyncpg` connect refused   | PostgreSQL is bound to `127.0.0.1` — verify `DATABASE_URL`     |
| Emails not sending                     | Check Gmail App Password validity; user may have rotated 2FA   |
| `Telegram Conflict: terminated by other getUpdates` | Two bot instances running. `systemctl status jyry-bot` on every host |
| Quota not resetting                    | Redis up? `redis-cli ping`; check `last_reset_on` in DB        |

---

## 12. Going further (post-launch)

- **Monitoring** — install `node_exporter` + a Hetzner Prometheus, alert on
  `systemctl is-failed` and disk > 80 %.
- **Log retention** — `journalctl --vacuum-time=14d` keeps the journal small.
- **Read-replica** — if traffic warrants, move PostgreSQL to a Hetzner Cloud
  Database and put a read-only replica in another region.
- **Geo-redundant webhook** — front the webhook with Cloudflare; Paddle
  retries on 5xx, so a brief outage is tolerable.
