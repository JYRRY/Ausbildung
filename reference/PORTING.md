# Porting plan: reference/gang → jyry/

Status: ✅ done · 🔜 next · ⏳ later · 💡 ideas only (stays in reference/) · ⛔ not ported (stays in reference/)

Nothing is deleted from `reference/gang/`. "Port" means: start from the GANG
code, move it to the server stack (async httpx, PostgreSQL, Settings), merge
it with what `jyry/` already has instead of duplicating, add tests, add the
improvements agreed with the product owner.

## Phase 1 — sending quality and the company directory

| GANG file | Target in jyry/ | Status | Notes |
|---|---|---|---|
| `src/services/email_extractor.py` | `services/email_extractor.py` | ✅ | admin/compliance blocklist, prefix variants, court/police domains (recruiting inbox allowed), portal support desks |
| `src/services/facility_facts_service.py` | `services/website_crawler.py` + contact extraction | 🔜 | Impressum/Kontakt contact person with role (Ausbildungsleiter, Personal), robots.txt |
| `src/services/website_crawler.py` | `services/website_crawler.py` | 🔜 | merge the best of both crawlers |
| `src/services/dasoertliche_scraper.py` | company directory: website/phone lookup | 🔜 | check the site's terms first |
| — (new) | company directory table + monthly refresh + change log | 🔜 | weekly Excel change report to admins |
| `src/core/locations.py` | `constants` / geo lookup | ⏳ | German places → state, coordinates for radius features |

## Phase 2 — applicant features

| GANG file | Target | Status | Notes |
|---|---|---|---|
| `src/services/profile_service.py` | multi-profile per user | ⏳ | |
| `src/services/bewerbung_pdf_service.py` | `services/bewerbungsmappe.py` | ⏳ | compare with the existing Bewerbungsmappe |
| `src/services/sender_pool_service.py` | SMTP test + per-account quota | ⏳ | no rotation to evade provider limits |
| `src/services/export_service.py`, `import_service.py` | admin/user export (Excel) | ⏳ | |
| `src/services/backup_service.py` | server backups | ⏳ | encrypted, off-site |
| `src/services/orchestrator.py` | `services/job_finder.py` / jobs | ⏳ | pipeline ideas |
| `src/services/jobsuche_scraper.py`, `jobsuche_api.py` | `services/bundesagentur.py` | ⏳ | jyry already on v6; compare for extra fields |
| `src/services/aubiplus_scraper.py`, `azubiyo_scraper.py`, `ausbildung_scraper.py` | extra vacancy sources | ⏳ | terms check per site; many of their ads already reach BA via partners |

## Ideas only / not ported

| GANG file | Status | Why |
|---|---|---|
| `src/ui/*` (dashboard, search, results, send, monitor, logs, settings, edit) | 💡 | reference for the Framer front end; screenshots in `screenshot_*.png` |
| `src/core/i18n.py`, `src/changelog.py` | 💡 | wording ideas |
| `src/services/maps_scraper.py` | ⛔ | Google blocks server IPs, breaks on UI changes, against Google's terms; Places API (free tier) instead |
| CAPTCHA solving (`src/ui/captcha_dialog.py`, ddddocr) | ⛔ | circumventing site protection |
| `src/core/security.py`, `src/ui/activation_dialog.py`, `security_overlay.py` | ⛔ | desktop licence gate, not needed on a server |
| `src/services/update_service.py`, `browser_installer.py`, `installer.*`, `build_with_browsers.py`, `*.spec`, `src/utils/win32_patch.py` | ⛔ | desktop packaging |
