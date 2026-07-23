# JYRY AI — Handoff Summary

_Last updated: session ending 2026-07-20. Paste this into a new session to continue._

> ⚠️ **No secrets in this file.** Framer/Proofly credentials, API keys, `.env`
> values, tokens etc. are intentionally omitted — fetch them from their source
> (Proofly plugin, Framer settings, the recovered `.env`). Never commit secrets.

---

## 1. Project goal

**JYRY AI** is a subscription SaaS that **auto-applies to German apprenticeship
(Ausbildung) positions** on behalf of Arabic/German-speaking job seekers. It:

1. Discovers matching vacancies via the **Bundesagentur für Arbeit REST API**.
2. Recovers the employer's contact email (from the posting, else by crawling the
   employer's own website).
3. Sends a personalised **German** application email from the user's **own Gmail**
   (SMTP + Google App Password), now with an auto-generated **Anschreiben PDF**
   attached per employer.

Primary market language: **German** (UI/emails). The operator (owner) communicates
in **Arabic**.

### Strategic pivot (in progress)
The product is being relaunched with a **Framer** front-end (the marketing site +
a new dashboard). The **FastAPI backend stays as the sole API**; the old Next.js
dashboard is being **deprecated** (not deleted until Framer reaches parity). The
Telegram bot remains as a companion/notifications channel.

---

## 2. Current architecture

Target production topology (single VM behind nginx, domain `bot.jyrygroup.com`
today, `api.jyrygroup.com` planned):

| Path / process | Role | systemd unit |
|---|---|---|
| `/api/*` → FastAPI | Dashboard/Framer API (port 8001) | `jyry-api.service` |
| `/webhook/paddle` | Paddle webhook (port 8080) | `jyry-webhook.service` |
| Telegram bot (long-poll) | Bot **+ owns the send scheduler (APScheduler)** | `jyry-bot.service` |
| `/app/*` → Next.js | Dashboard (being deprecated) | `jyry-web.service` |
| `/` static | Marketing site (being replaced by Framer) | nginx `/var/www/jyry` |
| PostgreSQL + Redis | DB + cache/quota | shared |

**Frontend pivot:** Framer front-end (temp domain `https://jyrygroup.framer.website`)
calls the FastAPI API cross-origin. The backend now supports this (see §7 + the
Framer auth work).

**Key architectural fact:** the **bot process owns the send scheduler**. A periodic
**re-sweep** (added this session) now picks up users activated on the web without
a bot restart.

---

## 3. Tech stack

| Layer | Choice |
|---|---|
| Bot | python-telegram-bot 21.x |
| Backend (bot + API + webhook) | FastAPI, SQLAlchemy 2 async, asyncpg, Pydantic v2, httpx |
| DB | PostgreSQL + Alembic (migrations 0001→**0008**) |
| Cache/queue/scheduler | Redis, APScheduler |
| Web auth | Google OAuth (openid+email+profile) + HS256 JWT (cookie **or** Bearer) |
| Payments | Paddle (Billing API, **sandbox** currently) |
| Crypto | Fernet (encrypts Gmail App Password) |
| PDF | reportlab (Anschreiben) + pypdf (merge) |
| Web uploads | python-multipart; local filesystem |
| Old frontend | Next.js 15 (App Router, basePath `/app`), TS, Tailwind v4 |
| **New frontend** | **Framer** (code components in TS/React; controlled via Proofly MCP) |

---

## 4. Important decisions

- **Anschreiben body** reuses the user's `email_draft.body_template` (rendered with
  `{{company}}`); no separate letter template field. Attached first, as `Anschreiben.pdf`.
- **Signature font:** Sacramento (SIL OFL), bundled in `jyry/assets/fonts/`.
- **Privacy rule (hard):** company/employer names are **never** exposed in
  bot/API/dashboard. Applications surface **job title + status only**. Source names
  ("Bundesagentur") removed from user-facing surfaces.
- **Framer auth:** temp domain is cross-site → **Bearer token is the active path**
  (token delivered via OAuth redirect `#token=` fragment, stored in `localStorage`).
  **Option A (same-site cookie)** is the target once a `jyrygroup.com` subdomain is
  connected to Framer (needs a paid Framer plan — deferred). Backend supports **both**.
- **Server host decision:** rebuild on **Hetzner Cloud**, plan **CX33** (Intel, 4 vCPU /
  8 GB / 80 GB, ~€8.99/mo), **Nürnberg**, **Ubuntu 24.04**, **☑ Backups**. NOT dedicated
  (overkill), NOT Oracle free tier (unreliable, was reclaimed). Billing = hourly capped
  at the monthly max; 20 TB traffic included (we'll never hit it). **Deferred: no budget yet.**
- **GANG/ZUGZWANG:** ideas only, **never** re-introduce that name into code/commits. Its
  BA approach (website scraping + CAPTCHA) is inferior to our REST API; its "AI" cover
  letters are a template merge (no LLM); only `email_extractor.py` was portable (already
  taken). Its multi-source **scraping engine is NOT in the `jyrry/gang` repo** (stripped);
  only the PyQt UI + email extractor + CAPTCHA solver remain. It's a **desktop app** — we
  borrow UX ideas, not code.
- **Source expansion** (AUBI-plus, then Ausbildung.de): deferred until a live server can
  reach those sites (the sandbox proxy blocks them + Bundesagentur with policy 403).

---

## 5. Current issues / bugs / blockers

- 🔴 **No live server.** The old Oracle Cloud (me-riyadh-1) free instance was reclaimed.
  The x86 boot volume (holds `.env` + Postgres data + `/opt/jyry`) is intact but can't
  boot on a free ARM shape. **Recovery path:** attach it as a secondary disk to a new VM,
  copy `.env` + DB dump, redeploy from git. **Nothing runs live until this is done.**
- 🔴 **Framer MCP is flaky.** The unframer/Proofly MCP relay disconnects/reconnects often
  in the session. Building works via the open plugin; **screenshots/headless tools need a
  Framer API key** registered with `setServerApiKey` (needs the `framer.com/projects/<id>`
  editor URL, NOT the published site URL — that was the sticking point).
- ⚠️ **Sandbox network policy** blocks outbound to non-allowlisted hosts (arbeitsagentur,
  aubi-plus, framer.website, published sites) with **403 at CONNECT** — cannot be bypassed;
  don't retry policy 403s. Use user-supplied screenshots to "see" external sites.
- ⚠️ **Remote branch deletion is blocked** (git server returns 403 on ref delete). The old
  working branch `claude/jyry-ai-handoff-c3aizj` may still exist on origin — the **user must
  delete it** from GitHub (it's fully merged into main; safe).
- ⚠️ **Test suite:** ~13 **pre-existing** failures are environmental (proxy 403 for
  Bundesagentur; a few stale bot-onboarding tests that no longer match handler logic).
  These are **not regressions**. Current: **375 passed / 13 failed**.
- ⚠️ **Paddle** is still sandbox; real price_ids not set; **no subscription-cancel endpoint**
  (the old Next.js button is a placeholder).
- ⚠️ **ruff debt** exists in pre-existing files (RUF001 ambiguous chars, I001 import order in
  `jyry/bot/main.py`, RUF003) — left untouched; there is no live CI enforcing ruff.

---

## 6. Completed this session (all on `main`)

Newest first (commit hashes on `main`):

- `33832de` **feat(bot):** collect postal address + phone in bot onboarding — new optional
  `ASK_CONTACT_DETAILS` step (between attachments & confirm) so Telegram users fill the
  Anschreiben letterhead. `repos.set_contact_details`, German messages + skip keyboard, tests.
- `831279d` **feat(scheduler):** periodic **re-sweep** — `sweep_active_users(only_missing=True)`
  + `add_resweep_job` (IntervalTrigger, default `SCHEDULER_RESWEEP_INTERVAL_SECONDS=120`) so
  web-activated users start sending without a bot restart. `has_job()`, tests.
- `a51bed3`/`78a1d73`/`8c27527` **feat(webapp):** cross-origin Framer support — `get_current_user`
  accepts **Bearer** + cookie; CORS from `WEB_CORS_ORIGINS`; cookie `Domain`/`SameSite`
  configurable; OAuth callback redirects to `WEB_APP_URL` with `#token=` fragment.
  `tests/webapp/test_cross_origin_auth.py`. (ruff: ignore B008 under `jyry/webapp/**`.)
- `bd42d80`/`34d2cfa` **docs:** `docs/framer-integration.md` — full API + auth + CORS guide,
  §0 current decision, §6a Bearer client, §4/§5 endpoint & data reference.
- `873111c`/`20e853e` **feat(dispatch):** wire **Bewerbungsmappe → send path**. Per-employer
  Anschreiben PDF generated and prepended as `Anschreiben.pdf`. User gains
  `postal_street`/`postal_plz_city`/`phone` (**migration 0008**). `JYRY_ANSCHREIBEN_ENABLED`
  flag. `build_betreff`/`strip_gender_suffix`/`city_from_plz_city`/`format_letter_date`
  helpers. API (`PATCH /api/profile`, `GET /api/me`, `GET /api/onboarding`) expose the fields.
  Never raises — a bad letter falls back to bare attachments.

**Also this session (not code):** created a Framer `StatCard.tsx` code component in the live
project (via Proofly MCP — verified rendering); produced a clickable dashboard prototype
Artifact (design reference, not published by user's choice); analysed the GANG desktop app.

### Completed in prior sessions (foundation)
Email extractor rewrite (7-strategy HTML), website crawler + dispatch wiring (migration 0007),
Bewerbungsmappe PDF service (reportlab/pypdf + Sacramento), web onboarding UI + backend,
ops CLIs (`set_plan`, `clear_applications`), Bundesagentur REST client, Gmail sender, deduper,
quota limiter, APScheduler scheduler, Paddle webhook, Google OAuth + JWT.

---

## 7. Remaining tasks (priority order)

| # | Task | Needs server? | Doable now (code)? |
|---|---|:---:|:---:|
| A | **Rebuild server** on Hetzner CX33 → recover `.env`+DB from old Oracle boot volume → redeploy from git → `alembic upgrade head` → `pip install` new deps (reportlab, pypdf, python-multipart) | 🔴 infra | — |
| B | Set Framer env on server: `WEB_CORS_ORIGINS`, `WEB_APP_URL` (temp Framer domain) | after A | — |
| C | **Build Framer front-end** (login, onboarding, dashboard/status, billing, marketing) on the canvas via Proofly MCP; wire each to the API with `fetch` once server is live | build now, wire after A | ✅ |
| D | Paddle: **subscription-cancel endpoint** (`POST /api/subscription/cancel`) + real price_ids + sandbox→production | partial | ✅ endpoint |
| E | Translate legal pages to German | — | ✅ |
| F | Edit the **Lebenslauf** template (user flagged) | — | ✅ |
| G | **AUBI-plus** scraper (httpx + schema.org JSON-LD), then Ausbildung.de | 🔴 (blocked here) | after A |
| H | Verify the website-crawler fix live (Pflegefachmann/Bayern should yield emails > 0) | 🔴 | after A |
| I | User: delete stale remote branch; retire Next.js `/app` once Framer at parity | — | user |

**Framer UX ideas borrowed from GANG (future screens):** a live **Monitor** view (send
progress, pause/resume), a **review-before-send** screen (preview Anschreiben+CV per employer),
an **email-deliverability** indicator, a richer **applications/CRM** table. Later/separate
product: **Google Maps B2B lead-gen**. Premium differentiator: **real LLM-personalised** Anschreiben.

---

## 8. File structure (key paths)

```
jyry/
├── config.py                      # Settings (env). New: anschreiben_enabled, web_cors_origins,
│                                  #   web_cookie_domain, web_cookie_samesite, web_app_url,
│                                  #   scheduler_resweep_interval_seconds
├── db/models.py                   # User gains postal_street/postal_plz_city/phone
├── services/
│   ├── bewerbungsmappe.py         # Anschreiben PDF (reportlab) + merge + build_betreff/anrede/date
│   ├── email_extractor.py         # 7-strategy HTML harvest + employer_website()
│   ├── website_crawler.py         # bounded async httpx crawler (fallback when no email)
│   ├── job_finder.py              # iter_ready_postings (BA search → cache → extract → crawl)
│   ├── send_pending.py            # dispatch_one: builds+prepends Anschreiben, resolves attachments
│   ├── scheduler.py               # JyryScheduler: sweep_active_users(only_missing), add_resweep_job, has_job
│   └── bundesagentur.py           # BA REST client
├── jobs/dispatch_tick.py          # tick_user + TickDeps (crawler, schedule_at, ...)
├── bot/
│   ├── main.py                    # ConversationHandler wiring; registers re-sweep job at startup
│   ├── handlers/onboarding.py     # + ASK_CONTACT_DETAILS (handle_contact_details/skip, back_from_contact)
│   ├── states.py                  # + ASK_CONTACT_DETAILS = 12
│   ├── keyboards.py               # + contact_details_keyboard, CB["contact_skip"]
│   ├── messages.py                # + ASK_CONTACT_DETAILS / CONTACT_SKIP_LABEL / CONTACT_SAVED (German)
│   └── repos.py                   # + set_contact_details
├── webapp/
│   ├── main.py                    # CORS from settings
│   ├── deps.py                    # get_current_user: cookie OR Bearer
│   ├── auth/jwt.py                # cookie Domain/SameSite from settings
│   ├── routes/{auth,me,profile,onboarding,applications,checkout,admin}.py
│   └── schemas.py                 # postal fields on MeOut/OnboardingOut/ProfilePatch
├── scripts/{set_plan,clear_applications}.py
└── assets/fonts/Sacramento-Regular.ttf
alembic/versions/…0008_user_postal_fields.py
tests/webapp/test_cross_origin_auth.py            # NEW
tests/services/test_scheduler.py                  # + re-sweep tests
tests/bot/test_handlers_onboarding.py             # + contact-details tests
docs/framer-integration.md                        # Framer integration guide
webapp/                                            # Next.js dashboard (being deprecated)
```

---

## 9. API structure (FastAPI, mounted at `/api`)

All authenticated endpoints accept the `jyry_session` **cookie** OR
`Authorization: Bearer <jwt>`. Send `credentials: "include"` (cookie) or the Bearer header.

- **Auth:** `GET /api/auth/google/login`, `GET /api/auth/google/callback`
  (redirects to `WEB_APP_URL#token=<jwt>` when set, else `/app`), `POST /api/auth/logout`.
- **Session/profile:** `GET /api/me` (incl. postal fields), `PATCH /api/profile`
  (`full_name`, `postal_street`, `postal_plz_city`, `phone`),
  `PUT /api/profile/app-password`, `PUT /api/notifications`, `PUT /api/active`.
- **Onboarding:** `GET /api/onboarding` (selection + catalog + plan limits + prefill),
  `PUT /api/onboarding/selection`, `PUT /api/onboarding/template`,
  `POST /api/onboarding/attachments` (PDF ≤10 MB, ≤8), `DELETE /api/onboarding/attachments/{i}`,
  `POST /api/onboarding/complete`.
- **Applications/billing:** `GET /api/applications` (job title + status **only**),
  `GET /api/checkout?plan=plus|pro|max` (302 → Paddle).
- **Admin/health:** `/api/admin/*`, `/api/health`. Docs at `/api/docs` (non-prod).

Relevant config env keys (values live in `.env`): `WEB_CORS_ORIGINS`, `WEB_APP_URL`,
`WEB_COOKIE_DOMAIN`, `WEB_COOKIE_SAMESITE`, `WEB_JWT_SECRET`, `JYRY_ANSCHREIBEN_ENABLED`,
`SCHEDULER_RESWEEP_INTERVAL_SECONDS`, `JYRY_TEST_REDIRECT_EMAIL`, `CRAWL_*`, `JYRY_UPLOAD_DIR`,
`FERNET_KEY`, `DATABASE_URL`, `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, Paddle keys, Google OAuth keys.

Plan limits (`jyry/constants.py`): quota free 10 / plus 30 / pro 100 / max 200;
max specialties free 1 / plus 3 / pro,max ∞; max states free 1 / plus 6 / pro,max ∞.
Prices: plus 14,99 / pro 29,99 / max 69,99 €.

---

## 10. Important instructions / working style

- **Git:** work on `main` (user overrode the harness's feature-branch rule and asked to push
  everything to `main` + delete the working branch). Commit identity **`Claude <noreply@anthropic.com>`**.
  Commit footer used: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` + a
  `Claude-Session:` line. A stop-hook and external automation (auto-PRs #36/#37, auto-merge to
  `main`) run in parallel — **always `git fetch` and reconcile before pushing**; expect divergence.
- **Do NOT create PRs** unless asked. **Never commit secrets** or the model identifier.
- **Language:** reply to the owner in **Arabic**; code/commits in English; bot & app UI in **German**.
- **Secrets:** keep out of chat; if one leaks, tell the user to rotate. (The user pasted Proofly
  MCP `projectId`/`secret`, a `prooflyToken`, and a Framer API key `fr_...` in chat — advise
  rotation when possible; unframer's secret couldn't be rotated.)
- **Framer control (Proofly MCP):** tools are `mcp__Framer__*`. Pass `projectId` + `secret`
  from the **Proofly plugin's "In-plugin" MCP URL card** (NOT the unframer URL). Project is
  **"JYRY GROUP"** (`875a3f70…a601d6`). Build tools work while the plugin is open (`ready:true`);
  screenshots/headless need `setServerApiKey(apiKey, projectUrl)` where `projectUrl` MUST be the
  `framer.com/projects/<id>` **editor** URL. Writes cost "Proofly Actions"; reads/screenshots free.
- **Framer project facts:** dark, blue/cyan brand ("Liquid Wave"); pages `/`, `/preise`,
  `/über-uns`, `/blog`, `/articles-2`, `/updates`. Color styles present are **experimental —
  do not rely on them**; palette not yet settled → build palette-neutral, prop-driven components.
  Fonts in use: **Satoshi** (display), **Inter** (UI), **Instrument Serif** (italic accent).
  A `StatCard.tsx` code component already exists in the project.
- **External sites:** the sandbox can't reach them (policy 403). Ask the user for screenshots.

---

## 11. What the next session must know first

1. **Read `docs/framer-integration.md`** — the frontend-backend contract is there.
2. **The engine is built; the blocker is infrastructure.** Priority is the **Hetzner server**
   (task A). Until then, nothing runs live and Framer components stay visual-only.
3. **Frontend ≠ backend.** Framer components are just UI until wired with `fetch` to the live API.
   Design now (static/mock), wire after the server exists.
4. **Reconcile git before pushing** (parallel automation moves `origin/main`).
5. **Tests:** 375 pass / 13 pre-existing env failures — not regressions.
6. **Respect the hard rules:** Arabic to owner, German UI, no company names to users, no secrets
   in commits, no GANG/ZUGZWANG attribution in code.
</content>
