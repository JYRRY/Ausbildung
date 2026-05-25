# JYRY AI

> Telegram bot that sends thousands of email applications to German Ausbildung
> companies in one click — straight from the user's own Gmail account.

JYRY AI fetches live Ausbildung postings from the Bundesagentur für Arbeit
Jobsuche API, extracts the employer's contact email, and queues the user's
templated cover letter for delivery via their personal Gmail account (SMTP +
App Password). Sending is paced and randomised inside a daytime window so the
mailbox does not look automated, and a per-user `UNIQUE(user_id, kundennummer)`
constraint guarantees the same employer is never contacted twice.

## Status

🚧 Early development. Tracking milestones M1 → M6. See repository commits for
progress.

## Tech stack

| Layer            | Choice                                        |
|------------------|-----------------------------------------------|
| Language         | Python 3.11                                   |
| Bot              | python-telegram-bot v21 (long-polling)        |
| Webhook / API    | FastAPI + Uvicorn                             |
| Database         | PostgreSQL 16 + SQLAlchemy 2 (async) + Alembic|
| Cache / queue    | Redis 7                                       |
| Scheduler        | APScheduler (AsyncIO)                         |
| Email            | aiosmtplib over Gmail SMTP (587, STARTTLS)    |
| Secrets at rest  | Fernet (cryptography)                         |
| Payments         | Paddle (Merchant of Record)            |
| Hosting          | Hetzner Cloud CX22 + systemd                  |
| License          | AGPL-3.0-or-later                             |

## Plans (EUR)

| Plan  | Price   | Duration   | Emails / day | Specialties | States  |
|-------|---------|------------|--------------|-------------|---------|
| Free  | 0 €     | 3-day trial| 5            | 1           | 1       |
| Plus  | 14.99 € | monthly    | 30           | 3 (choose)  | 6       |
| Pro   | 29.99 € | 3 months   | 100 spread   | all 13      | all 16  |
| Max   | 99 €    | yearly     | 100 spread   | all 13      | all 16 + 24/7 support |

## Supported specialties (13)

Pflegefachmann · Krankenpflegehelfer · Notfallsanitäter · Mechatroniker ·
Fachinformatiker für Anwendungsentwicklung · Fachinformatiker für
Systemintegration · Kaufmann · Bankkaufmann · Hotelfachmann · Verkäufer ·
Elektroniker · Bäcker · Koch.

## Supported states (16)

All 16 German Bundesländer.

## Repository layout (planned)

```
jyry/
├── bot/                 # Telegram handlers, FSM, keyboards
├── services/            # bundesagentur, email_extractor, gmail_sender,
│                        # scheduler, deduper, rate_limiter, crypto
├── db/                  # SQLAlchemy models + session factory
├── payments/            # Paddle client + FastAPI webhook
└── config.py
alembic/                 # migrations
deploy/                  # systemd unit + Hetzner runbook
tests/
```

## Local development

```bash
cp .env.example .env
# generate a Fernet key and paste into FERNET_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
jyry-bot          # Telegram long-polling worker
jyry-webhook      # Paddle webhook receiver
```

## Compliance notice

Unsolicited bulk email to German employers can run afoul of the UWG (§7
unlautere Werbung) and GDPR, and Gmail itself rate-limits accounts that send
many emails to recipients who have no prior relationship. JYRY AI therefore:

* sends only from the **end user's own Gmail account** via their App Password,
* paces deliveries inside a daytime window with random jitter,
* refuses to contact the same employer twice for the same user,
* surfaces an explicit warning during onboarding before the first send.

The end user remains the sender of record and is responsible for the content
and lawfulness of their applications.

## License

[AGPL-3.0-or-later](LICENSE) — if you run a modified version of this bot as a
network service, you must publish your source modifications under the same
license.
