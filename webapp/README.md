# JYRY AI — Web Dashboard

Next.js 15 dashboard for `bot.jyrygroup.com/app`. Talks to the FastAPI
backend in `jyry/webapp/` (running on the same box at `127.0.0.1:8001`).

## Local development

```bash
# from this folder
cp .env.example .env.local
npm install
npm run dev   # → http://localhost:3000/app
```

Run the FastAPI side in another terminal from the repo root:

```bash
WEB_JWT_SECRET=devsecret \
GOOGLE_CLIENT_ID=... \
GOOGLE_CLIENT_SECRET=... \
WEB_PUBLIC_URL=http://localhost:3000 \
python -m jyry.webapp.main
```

## Production

`npm run build` produces a standalone server (`.next/standalone/`).
The systemd unit (`deploy/systemd/jyry-web.service`) launches it on
`127.0.0.1:3000`; nginx proxies `/app/*` to it.

## Pages

| Path                 | Visibility   | Description                                |
|----------------------|--------------|--------------------------------------------|
| `/app/signin`        | public       | Google OAuth entry                         |
| `/app/dashboard`     | logged-in    | overview + recent activity                 |
| `/app/applications`  | logged-in    | paginated send history (no company names)  |
| `/app/profile`       | logged-in    | name, gmail, app password, notif, pause    |
| `/app/subscription`  | logged-in    | plan + upgrade buttons                     |
| `/app/admin`         | is_admin     | global stats + users table                 |
