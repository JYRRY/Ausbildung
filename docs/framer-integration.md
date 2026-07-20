# Framer integration guide

How the JYRY AI product moves from the current **Next.js dashboard** (served at
`bot.jyrygroup.com/app`) to a **Framer** front-end, while keeping the FastAPI
backend as the single API.

> Status legend used throughout:
> **[EXISTS]** already in the codebase today ·
> **[TODO]** a backend change this migration needs (not yet implemented).

---

## 1. What changes and what stays

| Layer | Today | After Framer |
|---|---|---|
| Marketing site | static pages in `/var/www/jyry` (nginx) | **Framer** ("Ausbildung service" section) |
| Dashboard UI | Next.js on `/app` (`jyry-web.service`, :3000) | **Framer** (custom code components) |
| API | FastAPI `/api/*` (`jyry-api.service`, :8001) | **unchanged** — Framer calls it |
| Auth | Google OAuth → HS256 JWT in `HttpOnly` cookie | same JWT, **cookie/CORS reworked for cross-origin** |
| Bot | Telegram bot + send scheduler | **unchanged** (companion channel) |
| DB / Redis | PostgreSQL + Redis | **unchanged** |

The backend does not need to be rewritten. The whole integration is:
1. make the API reachable and authenticated **cross-origin** from a Framer host, and
2. have Framer code components call the existing endpoints.

Framer has no server, so **all business logic stays in FastAPI**. Framer only
renders UI and calls `/api/*`.

---

## 2. The core problem: cross-origin authentication

Today the dashboard and the API share one origin (`bot.jyrygroup.com`), so the
session cookie "just works". Framer sites are hosted on a **different origin**
(either `*.framer.website` or a custom domain), which breaks two assumptions.

Current cookie (`jyry/webapp/auth/jwt.py`, `set_session_cookie`) **[EXISTS]**:

```
Set-Cookie: jyry_session=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/
```

- `SameSite=Lax` → the cookie is **only sent on top-level navigations**, not on
  cross-site `fetch()`/`XHR`. A Framer page doing `fetch('.../api/me')` on a
  different site will send **no cookie** → `401`.
- Host-only cookie (no `Domain`) → scoped to `bot.jyrygroup.com` only, never to a
  sibling subdomain.
- `HttpOnly` → Framer JS cannot read the token, so it cannot fall back to putting
  it in an `Authorization` header without a separate delivery mechanism.

Plus CORS: `allow_origins` is a hardcoded list (`jyry/webapp/main.py`) that does
not include any Framer origin **[EXISTS]**.

There are three ways to resolve this. Pick **one**.

### Option A — Custom subdomain, same registrable domain *(recommended)*

Serve Framer under the **same registrable domain** as the API:

- Framer front-end → `www.jyrygroup.com` (or `app.jyrygroup.com`)
- API → `api.jyrygroup.com` (or keep `bot.jyrygroup.com`)

Because both share `jyrygroup.com`, requests between them are **same-site**
(cross-origin but same-site). `SameSite=Lax` cookies **are** sent on same-site
XHR, and a `Domain=.jyrygroup.com` cookie is visible to every subdomain.

Backend changes:
- Widen the cookie with `Domain=.jyrygroup.com` **[TODO]**.
- Add the Framer origin to CORS `allow_origins` **[TODO]**.
- Keep `SameSite=Lax` (no third-party-cookie risk).

Pros: robust, no third-party-cookie deprecation exposure, cookie stays
`HttpOnly` (XSS-safe). Cons: requires pointing a `jyrygroup.com` subdomain at
Framer (Framer supports custom domains).

### Option B — Framer default domain + `SameSite=None`

Keep Framer on `*.framer.website`. Requests are then **cross-site**, so the
cookie must be:

```
Set-Cookie: jyry_session=<jwt>; HttpOnly; Secure; SameSite=None; Path=/
```

Backend changes: `SameSite=None` on the session cookie **[TODO]** + CORS origin
**[TODO]**.

Cons: `SameSite=None` cookies are **third-party cookies**. Safari (ITP) blocks
them today and Chrome is phasing them out. **Fragile — not recommended** for the
long term. Fine only for a quick internal demo.

### Option C — Bearer token (no cookie)

After OAuth, deliver the JWT to Framer (URL fragment on redirect), Framer stores
it (e.g. `localStorage`) and sends it as `Authorization: Bearer <jwt>` on every
call. `get_current_user` accepts the header in addition to the cookie.

Backend changes: token delivery on the OAuth redirect **[TODO]** + Bearer parsing
in `get_current_user` **[TODO]**.

Pros: works on any origin, immune to third-party-cookie blocking. Cons: token is
readable by JS → XSS can exfiltrate it; you own token storage/refresh.

**Recommendation:** ship **Option A**. Keep **Option C** as the documented
fallback if a `jyrygroup.com` subdomain for Framer is not acceptable.

---

## 3. Backend changes required (Option A)

All small, all config-driven. None are applied yet — this section is the work
list.

### 3.1 Config `jyry/config.py` **[TODO]**

```python
# Comma-separated list of browser origins allowed to call the API with creds.
web_cors_origins: list[str] = Field(
    default_factory=list, alias="WEB_CORS_ORIGINS"
)
# Cookie Domain for the session cookie. ".jyrygroup.com" shares it across
# subdomains; leave None for a host-only cookie (current behaviour).
web_cookie_domain: str | None = Field(default=None, alias="WEB_COOKIE_DOMAIN")
# SameSite policy for the session cookie: "lax" (same-site) or "none" (cross-site).
web_cookie_samesite: str = Field(default="lax", alias="WEB_COOKIE_SAMESITE")
# Where the OAuth callback lands the user (the Framer app URL).
web_app_url: str | None = Field(default=None, alias="WEB_APP_URL")
```

Add a validator that splits `WEB_CORS_ORIGINS` on commas (mirror
`_split_admin_ids`).

### 3.2 CORS `jyry/webapp/main.py` **[TODO]**

Build `allow_origins` from `settings.web_cors_origins` (falling back to the
current defaults) instead of the hardcoded list. `allow_credentials=True` is
already set; note that with credentials you **cannot** use `"*"` — origins must
be explicit.

### 3.3 Session cookie `jyry/webapp/auth/jwt.py` **[TODO]**

`set_session_cookie` / `clear_session_cookie` should pass
`domain=settings.web_cookie_domain` and
`samesite=settings.web_cookie_samesite`. Everything else stays.

### 3.4 OAuth redirect `jyry/webapp/routes/auth.py` **[TODO]**

`google_callback` currently redirects to `f"{web_public_url}/app"`. Change the
target to `settings.web_app_url or f"{web_public_url}/app"` so sign-in lands on
the Framer app, not the deprecated Next.js page. (For Option C, also append the
token as a `#token=…` fragment here.)

> The `jyry_oauth_state` cookie is set with `Path=/api/auth` and `SameSite=Lax`.
> The OAuth flow is a **top-level navigation** (the browser is redirected to
> Google and back), so `Lax` is correct for it and needs no change under Option A.

### 3.5 Optional Bearer support (only for Option C) **[TODO]**

In `get_current_user`, if the cookie is absent, read
`Authorization: Bearer <jwt>` and decode the same way. Keep cookie support so the
bot-linked/web flows are unaffected.

---

## 4. API reference (as it exists today) **[EXISTS]**

Base path: `/api`. All authenticated endpoints require the `jyry_session` cookie
(Option A/B) or Bearer token (Option C). Send `credentials: 'include'` on every
`fetch` from Framer.

### Auth
| Method | Path | Notes |
|---|---|---|
| GET | `/api/auth/google/login` | Redirects to Google. Link the Framer "Login" button straight here (top-level navigation, not `fetch`). |
| GET | `/api/auth/google/callback` | Google redirects here; sets the session cookie and redirects to the app. |
| POST | `/api/auth/logout` | Clears the cookie. `204`. |

### Session & profile
| Method | Path | Body → | Returns |
|---|---|---|---|
| GET | `/api/me` | — | `MeOut` (user, subscription, counters). Includes `postal_street`, `postal_plz_city`, `phone`. |
| PATCH | `/api/profile` | `{full_name?, postal_street?, postal_plz_city?, phone?}` | `{ok}` — Anschreiben letterhead fields. |
| PUT | `/api/profile/app-password` | `{app_password}` (16 chars) | `{ok}` — Gmail App Password (encrypted server-side). |
| PUT | `/api/notifications` | `{mode}` (`per_send`\|`daily`\|`off`) | `{ok}` |
| PUT | `/api/active` | `{is_active}` | `{ok}` — pause/resume sending. |

### Onboarding / setup
| Method | Path | Body → | Returns |
|---|---|---|---|
| GET | `/api/onboarding` | — | `OnboardingOut`: current selection, full catalog (`all_specialties`, `all_states`), plan limits, readiness flags, and the postal fields for prefill. |
| PUT | `/api/onboarding/selection` | `{specialties:[kw], states:[code]}` | `{ok}` — enforces plan max. |
| PUT | `/api/onboarding/template` | `{subject_template, body_template}` | `{ok}` — `{{company}}` placeholder supported. |
| POST | `/api/onboarding/attachments` | `multipart/form-data` file (PDF ≤10 MB, ≤8 total) | `{ok}` |
| DELETE | `/api/onboarding/attachments/{index}` | — | `{ok}` |
| POST | `/api/onboarding/complete` | — | `{ok, onboarding_complete}` — requires all readiness checks. |

### Applications & billing
| Method | Path | Query | Returns |
|---|---|---|---|
| GET | `/api/applications` | `page, page_size, status?` | `ApplicationsPage`. **Job title only — never company names** (privacy rule). |
| GET | `/api/checkout?plan=plus\|pro\|max` | — | `302` to Paddle checkout. Navigate the browser to it, don't `fetch`. |

### Admin (`is_admin` only) & health
`/api/admin/stats`, `/api/admin/users`, `/api/admin/users/{id}/grant-trial`,
`/api/admin/users/{id}/toggle-active`, `/api/admin/users/{id}/promote`,
`/api/admin/health`, and unauthenticated `/api/health`.

Interactive schema (non-prod): `GET /api/docs`.

---

## 5. Data the Framer onboarding forms need

`GET /api/onboarding` returns everything a self-contained setup UI needs — you do
not hardcode catalogs in Framer:

- `all_specialties`: `[{keyword, label_de, label_ar}]` — the 13 supported
  Ausbildung fields, with Arabic + German labels.
- `all_states`: `[{code, label_de, label_ar}]` — the 16 Bundesländer.
- `max_specialties` / `max_states`: plan cap (`null` = unlimited). Enforce in the
  UI **and** rely on the server (it re-checks and returns `400` with a German
  message on overflow).
- `has_app_password`, `ready`, `onboarding_complete`, `plan`.
- `postal_street`, `postal_plz_city`, `phone`, `subject_template`,
  `body_template`, `attachments` for prefill.

Plan limits (from `jyry/constants.py`, for reference):

| Plan | daily quota | max specialties | max states |
|---|---|---|---|
| free | 10 | 1 | 1 |
| plus | 30 | 3 | 6 |
| pro | 100 | ∞ | ∞ |
| max | 200 | ∞ | ∞ |

A user is **ready to send** once they have: signed in (Gmail pinned to the login
address), set an App Password, a non-empty subject template, ≥1 specialty and ≥1
state. The postal/phone fields are **optional** — missing lines are simply
omitted from the generated Anschreiben.

---

## 6. Example calls from a Framer code component

```ts
const API = "https://api.jyrygroup.com" // your API origin

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",            // REQUIRED — sends the session cookie
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  })
  if (res.status === 401) { window.location.href = `${API}/api/auth/google/login`; return }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

// Login button → top-level navigation (NOT fetch), so Google can redirect back:
// <a href={`${API}/api/auth/google/login`}>Mit Google anmelden</a>

const me = await api("/api/me")
const onboarding = await api("/api/onboarding")
await api("/api/onboarding/selection", {
  method: "PUT",
  body: JSON.stringify({ specialties: ["Pflegefachmann"], states: ["BY"] }),
})

// PDF upload uses multipart — do NOT set Content-Type manually:
async function uploadCv(file: File) {
  const fd = new FormData(); fd.append("file", file)
  const res = await fetch(`${API}/api/onboarding/attachments`, {
    method: "POST", credentials: "include", body: fd,
  })
  if (!res.ok) throw new Error(await res.text())
}
```

Notes:
- **Login and checkout are navigations, not `fetch`** — the browser must follow
  the `302`s (to Google, to Paddle).
- Never set `Content-Type` on the multipart upload; the browser sets the boundary.
- On `401`, bounce to `/api/auth/google/login`.

---

## 7. Rollout plan

1. Point a `jyrygroup.com` subdomain at Framer (e.g. `www`), and an `api`
   subdomain at the FastAPI service (nginx).
2. Land backend §3 changes; set env: `WEB_CORS_ORIGINS=https://www.jyrygroup.com`,
   `WEB_COOKIE_DOMAIN=.jyrygroup.com`, `WEB_APP_URL=https://www.jyrygroup.com/app`.
3. Update the Google OAuth **authorized redirect URI** to the API origin's
   `/api/auth/google/callback` if the API host changes.
4. Build the Framer screens against §4/§5, using §6 as the client contract.
5. Verify end-to-end: login → onboarding → mark active → a send fires (needs the
   live server + scheduler).
6. Once Framer is at parity, retire `jyry-web.service` and the `/app` nginx
   route. Keep the API, bot, and webhook services.

## 8. Open questions

- **Session refresh:** the JWT lasts `WEB_SESSION_DAYS` (default 7) with no
  refresh endpoint. Framer should treat a `401` as "log in again". A silent
  refresh endpoint can be added later if needed.
- **Scheduler activation gap:** flipping `is_active` via `/api/active` does **not**
  notify the running send scheduler — the bot only picks up newly-active users at
  startup (`sweep_active_users`). A periodic re-sweep is a separate, known task;
  until then, web-driven activation is not real-time.
- **Subscription cancel:** there is no cancel endpoint yet (the Next.js button is
  a placeholder). Add a `POST /api/subscription/cancel` (Paddle API) before
  Framer exposes a cancel button.
</content>
</invoke>
