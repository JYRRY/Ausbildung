/**
 * Tiny i18n for the dashboard. German is the primary language; English is the
 * toggle. The active language lives in a `jyry_lang` cookie so both server
 * components (read via next/headers) and the toggle (client) agree.
 */

export type Lang = "de" | "en";
export const DEFAULT_LANG: Lang = "de";
export const LANG_COOKIE = "jyry_lang";

type Dict = Record<string, string>;

const de: Dict = {
  // generic
  "nav.dashboard": "Dashboard",
  "nav.applications": "Bewerbungen",
  "nav.profile": "Profil",
  "nav.subscription": "Abo",
  "nav.admin": "Admin",
  "nav.setup": "Einrichtung",
  "nav.subtitle": "Dashboard",
  "action.logout": "Abmelden",
  "common.none": "—",

  // setup / onboarding
  "setup.title": "Einrichtung",
  "setup.lead":
    "Vervollständige dein Setup, damit der automatische Versand starten kann.",
  "setup.banner_incomplete":
    "Dein Setup ist noch nicht vollständig. Schließe die Einrichtung ab, um den Versand zu starten.",
  "setup.banner_cta": "Einrichtung abschließen",
  "setup.specialties_title": "Fachrichtungen",
  "setup.specialties_hint": "Wähle die Ausbildungsberufe, auf die du dich bewerben möchtest.",
  "setup.states_title": "Bundesländer",
  "setup.states_hint": "Wähle die Bundesländer, in denen gesucht werden soll.",
  "setup.limit_reached": "Tarif-Limit erreicht: maximal {n}.",
  "setup.limit_unlimited": "Alle verfügbar in deinem Tarif.",
  "setup.limit_count": "{c} von {n} ausgewählt.",
  "setup.template_title": "E-Mail-Vorlage",
  "setup.template_hint": "Nutze {{company}} als Platzhalter für den Firmennamen.",
  "setup.subject_label": "Betreff",
  "setup.body_label": "Nachrichtentext",
  "setup.attachments_title": "Anhänge (Lebenslauf etc.)",
  "setup.attachments_hint": "Nur PDF, max. 10 MB pro Datei, bis zu 8 Dateien.",
  "setup.attachments_upload": "PDF hochladen",
  "setup.attachments_uploading": "Wird hochgeladen…",
  "setup.attachments_empty": "Noch keine Anhänge.",
  "setup.attachments_from_bot": "über Telegram",
  "setup.delete": "Entfernen",
  "setup.ready_title": "Bereit zum Versand",
  "setup.ready_done": "✅ Dein Setup ist vollständig.",
  "setup.ready_missing": "Es fehlt noch: {items}",
  "setup.miss_app_password": "App-Passwort (im Profil)",
  "setup.miss_specialties": "mind. eine Fachrichtung",
  "setup.miss_states": "mind. ein Bundesland",
  "setup.miss_template": "E-Mail-Betreff",
  "setup.complete_btn": "Einrichtung abschließen",
  "setup.completed": "✅ Einrichtung abgeschlossen.",

  // signin
  "signin.title": "Bei JYRY AI anmelden",
  "signin.lead":
    "Melde dich mit deinem Google-Konto an, um dein Dashboard, deine Bewerbungen und dein Abo zu verwalten.",
  "signin.google": "Mit Google fortfahren",
  "signin.terms_prefix": "Mit der Anmeldung stimmst du unseren ",
  "signin.terms": "Nutzungsbedingungen",
  "signin.and": " und der ",
  "signin.privacy": "Datenschutzerklärung",
  "signin.terms_suffix": " zu.",

  // dashboard
  "dash.welcome": "Willkommen",
  "dash.lead": "Hier ist der Überblick über deinen Versand und dein Abo.",
  "dash.sent_today": "Heute versendet",
  "dash.remaining": "{n} verbleibend von {q}",
  "dash.no_sub": "Kein Abo",
  "dash.plan": "Tarif",
  "dash.shipping": "Versand",
  "dash.active": "aktiv",
  "dash.paused": "pausiert",
  "dash.setup_done": "Setup abgeschlossen",
  "dash.setup_incomplete": "Setup unvollständig",
  "dash.expires": "Läuft bis",
  "dash.recent": "Letzte Aktivität",
  "dash.no_recent": "Noch keine Bewerbungen versendet.",
  "col.position": "Stelle",
  "col.status": "Status",
  "col.date": "Datum",

  // versand toggle
  "versand.running": "Versand läuft",
  "versand.paused": "Versand pausiert",
  "versand.running_hint":
    "Bewerbungen werden über den Tag verteilt verschickt.",
  "versand.paused_hint":
    "Der Versand ist gestoppt. Schalte ihn wieder ein, um fortzusetzen.",
  "versand.pause": "Pausieren",
  "versand.resume": "Fortsetzen",

  // applications
  "apps.title": "Bewerbungen",
  "apps.lead": "Verlauf aller versendeten Bewerbungen.",
  "apps.privacy_note":
    "(Aus Datenschutzgründen wird der Firmenname nicht angezeigt.)",
  "apps.empty": "Noch keine Bewerbungen.",
  "apps.col_sent": "Versendet",
  "apps.col_queued": "Eingereiht",
  "apps.page_of": "Seite {p} von {last} — {total} insgesamt",
  "apps.prev": "← Zurück",
  "apps.next": "Weiter →",

  // profile
  "profile.title": "Profil",
  "profile.lead":
    "Verwalte deinen Absendernamen, dein Gmail-Konto und deine Benachrichtigungen.",
  "profile.personal": "Persönliche Daten",
  "profile.notifications": "Benachrichtigungen",
  "profile.gmail_label": "Gmail-Adresse (Versand)",
  "profile.gmail_locked": "gesperrt",
  "profile.gmail_hint":
    "Bewerbungen werden von deinem Anmelde-Konto versendet. Diese Adresse ist fest mit deinem Google-Login verknüpft und kann nicht geändert werden.",
  "profile.name_label": "Absendername",
  "profile.name_placeholder": "Vor- und Nachname",
  "profile.apppw_label": "Google App-Passwort",
  "profile.apppw_saved": "(bereits gespeichert — nur ausfüllen, um zu ändern)",
  "profile.apppw_help_show": "Wie erstelle ich ein App-Passwort?",
  "profile.apppw_help_hide": "Anleitung ausblenden",
  "profile.required": "Pflichtfeld",
  "profile.apppw_len": "App-Passwort muss genau 16 Zeichen lang sein.",
  "profile.fill_required": "Bitte fülle die markierten Pflichtfelder aus.",
  "profile.saved": "✅ Profil gespeichert.",
  "action.save": "Speichern",
  "action.saving": "Speichern…",
  "action.cancel": "Abbrechen",
  "apppw.steps_title": "App-Passwort in 4 Schritten erstellen:",
  "apppw.step1_a": "Aktiviere die ",
  "apppw.step1_link": "Bestätigung in zwei Schritten (2FA)",
  "apppw.step1_b": " — ohne 2FA gibt es keine App-Passwörter.",
  "apppw.step2_a": "Öffne ",
  "apppw.step2_b": ".",
  "apppw.step3_a": "Gib einen Namen ein (z. B. JYRY AI) und klicke auf ",
  "apppw.step3_b": "Erstellen",
  "apppw.step3_c": ".",
  "apppw.step4":
    "Google zeigt ein 16-stelliges Passwort (in 4 Blöcken). Kopiere es und füge es oben ein — mit oder ohne Leerzeichen.",
  "apppw.footer":
    "Das Passwort wird verschlüsselt gespeichert und ausschließlich für den E-Mail-Versand über dein Gmail-Konto verwendet.",

  // notifications
  "notif.per_send": "🔔 Pro Bewerbung",
  "notif.per_send_hint":
    "Nachricht im Telegram-Bot nach jeder gesendeten Bewerbung.",
  "notif.daily": "📊 Tagesbericht",
  "notif.daily_hint": "Eine Zusammenfassung am Ende des Tages.",
  "notif.off": "🔕 Aus",
  "notif.off_hint": "Keine Benachrichtigungen.",

  // subscription
  "sub.title": "Abo",
  "sub.lead": "Aktueller Tarif, Verlängerung und Upgrade-Optionen.",
  "sub.current": "Aktueller Tarif",
  "sub.status": "Status",
  "sub.no_sub": "kein Abo",
  "sub.expires": "Läuft bis",
  "sub.compare": "Tarife im Vergleich",
  "sub.emails_day": "E-Mails / Tag",
  "sub.upgrade": "Upgrade",
  "sub.current_plan": "Aktueller Tarif",
  "sub.footer":
    "Upgrades werden anteilig nach Nutzung berechnet. Die Abwicklung erfolgt über Paddle; Verlängerungen sind automatisch und können jederzeit deaktiviert werden.",
  "sub.free_period": "3 Tage Testphase",
  "sub.plus_period": "pro Monat",
  "sub.pro_period": "alle 3 Monate",
  "sub.max_period": "alle 6 Monate",
  "sub.f_1beruf": "1 Beruf",
  "sub.f_1land": "1 Bundesland",
  "sub.f_3berufe": "3 Berufe",
  "sub.f_6laender": "6 Bundesländer",
  "sub.f_allberufe": "Alle Berufe",
  "sub.f_alllaender": "Alle 16 Bundesländer",
  "sub.f_templates": "Bewerbungs-Vorlagen",
  "sub.f_support": "24/7 Priority-Support",

  // admin
  "admin.title": "Admin",
  "admin.lead": "Übersicht über alle Nutzer, Tarife und Aktivität.",
  "admin.users_total": "Nutzer insgesamt",
  "admin.users_active": "Davon aktiv",
  "admin.emails_today": "E-Mails heute",
  "admin.emails_total": "E-Mails gesamt",
  "admin.users": "Nutzer",
  "admin.search": "Suche nach E-Mail oder Name…",
  "admin.col_name": "Name",
  "admin.col_plan": "Tarif",
  "admin.col_today": "Heute",
  "admin.col_total": "Gesamt",
  "admin.col_created": "Erstellt",
};

const en: Dict = {
  "nav.dashboard": "Dashboard",
  "nav.applications": "Applications",
  "nav.profile": "Profile",
  "nav.subscription": "Subscription",
  "nav.admin": "Admin",
  "nav.setup": "Setup",
  "nav.subtitle": "Dashboard",
  "action.logout": "Sign out",
  "common.none": "—",

  // setup / onboarding
  "setup.title": "Setup",
  "setup.lead": "Complete your setup so automatic sending can start.",
  "setup.banner_incomplete":
    "Your setup isn't complete yet. Finish it to start sending.",
  "setup.banner_cta": "Finish setup",
  "setup.specialties_title": "Specialties",
  "setup.specialties_hint": "Pick the apprenticeships you want to apply for.",
  "setup.states_title": "Federal states",
  "setup.states_hint": "Pick the states to search in.",
  "setup.limit_reached": "Plan limit reached: max {n}.",
  "setup.limit_unlimited": "All available on your plan.",
  "setup.limit_count": "{c} of {n} selected.",
  "setup.template_title": "Email template",
  "setup.template_hint": "Use {{company}} as a placeholder for the company name.",
  "setup.subject_label": "Subject",
  "setup.body_label": "Message body",
  "setup.attachments_title": "Attachments (CV etc.)",
  "setup.attachments_hint": "PDF only, max 10 MB each, up to 8 files.",
  "setup.attachments_upload": "Upload PDF",
  "setup.attachments_uploading": "Uploading…",
  "setup.attachments_empty": "No attachments yet.",
  "setup.attachments_from_bot": "via Telegram",
  "setup.delete": "Remove",
  "setup.ready_title": "Ready to send",
  "setup.ready_done": "✅ Your setup is complete.",
  "setup.ready_missing": "Still missing: {items}",
  "setup.miss_app_password": "App password (in Profile)",
  "setup.miss_specialties": "at least one specialty",
  "setup.miss_states": "at least one state",
  "setup.miss_template": "email subject",
  "setup.complete_btn": "Finish setup",
  "setup.completed": "✅ Setup complete.",

  "signin.title": "Sign in to JYRY AI",
  "signin.lead":
    "Sign in with your Google account to manage your dashboard, applications and subscription.",
  "signin.google": "Continue with Google",
  "signin.terms_prefix": "By signing in you agree to our ",
  "signin.terms": "Terms of Service",
  "signin.and": " and ",
  "signin.privacy": "Privacy Policy",
  "signin.terms_suffix": ".",

  "dash.welcome": "Welcome",
  "dash.lead": "Here's the overview of your sending and subscription.",
  "dash.sent_today": "Sent today",
  "dash.remaining": "{n} remaining of {q}",
  "dash.no_sub": "No subscription",
  "dash.plan": "Plan",
  "dash.shipping": "Sending",
  "dash.active": "active",
  "dash.paused": "paused",
  "dash.setup_done": "Setup complete",
  "dash.setup_incomplete": "Setup incomplete",
  "dash.expires": "Valid until",
  "dash.recent": "Recent activity",
  "dash.no_recent": "No applications sent yet.",
  "col.position": "Position",
  "col.status": "Status",
  "col.date": "Date",

  "versand.running": "Sending is running",
  "versand.paused": "Sending is paused",
  "versand.running_hint": "Applications are sent spread out over the day.",
  "versand.paused_hint":
    "Sending is stopped. Turn it back on to continue.",
  "versand.pause": "Pause",
  "versand.resume": "Resume",

  "apps.title": "Applications",
  "apps.lead": "History of all sent applications.",
  "apps.privacy_note":
    "(For privacy reasons the company name is not shown.)",
  "apps.empty": "No applications yet.",
  "apps.col_sent": "Sent",
  "apps.col_queued": "Queued",
  "apps.page_of": "Page {p} of {last} — {total} total",
  "apps.prev": "← Previous",
  "apps.next": "Next →",

  "profile.title": "Profile",
  "profile.lead":
    "Manage your sender name, Gmail account and notifications.",
  "profile.personal": "Personal details",
  "profile.notifications": "Notifications",
  "profile.gmail_label": "Gmail address (sending)",
  "profile.gmail_locked": "locked",
  "profile.gmail_hint":
    "Applications are sent from your sign-in account. This address is permanently tied to your Google login and cannot be changed.",
  "profile.name_label": "Sender name",
  "profile.name_placeholder": "First and last name",
  "profile.apppw_label": "Google App Password",
  "profile.apppw_saved": "(already saved — only fill in to change)",
  "profile.apppw_help_show": "How do I create an App Password?",
  "profile.apppw_help_hide": "Hide instructions",
  "profile.required": "Required",
  "profile.apppw_len": "App Password must be exactly 16 characters.",
  "profile.fill_required": "Please fill in the required fields.",
  "profile.saved": "✅ Profile saved.",
  "action.save": "Save",
  "action.saving": "Saving…",
  "action.cancel": "Cancel",
  "apppw.steps_title": "Create an App Password in 4 steps:",
  "apppw.step1_a": "Enable ",
  "apppw.step1_link": "2-Step Verification (2FA)",
  "apppw.step1_b": " — without 2FA there are no App Passwords.",
  "apppw.step2_a": "Open ",
  "apppw.step2_b": ".",
  "apppw.step3_a": "Enter a name (e.g. JYRY AI) and click ",
  "apppw.step3_b": "Create",
  "apppw.step3_c": ".",
  "apppw.step4":
    "Google shows a 16-character password (in 4 blocks). Copy it and paste it above — with or without spaces.",
  "apppw.footer":
    "The password is stored encrypted and used only to send email through your Gmail account.",

  "notif.per_send": "🔔 Per application",
  "notif.per_send_hint":
    "A Telegram message after each application is sent.",
  "notif.daily": "📊 Daily report",
  "notif.daily_hint": "A summary at the end of the day.",
  "notif.off": "🔕 Off",
  "notif.off_hint": "No notifications.",

  "sub.title": "Subscription",
  "sub.lead": "Current plan, renewal and upgrade options.",
  "sub.current": "Current plan",
  "sub.status": "Status",
  "sub.no_sub": "no subscription",
  "sub.expires": "Valid until",
  "sub.compare": "Compare plans",
  "sub.emails_day": "emails / day",
  "sub.upgrade": "Upgrade",
  "sub.current_plan": "Current plan",
  "sub.footer":
    "Upgrades are prorated by usage. Billing is handled by Paddle; renewals are automatic and can be cancelled anytime.",
  "sub.free_period": "3-day trial",
  "sub.plus_period": "per month",
  "sub.pro_period": "every 3 months",
  "sub.max_period": "every 6 months",
  "sub.f_1beruf": "1 profession",
  "sub.f_1land": "1 federal state",
  "sub.f_3berufe": "3 professions",
  "sub.f_6laender": "6 federal states",
  "sub.f_allberufe": "All professions",
  "sub.f_alllaender": "All 16 federal states",
  "sub.f_templates": "Application templates",
  "sub.f_support": "24/7 priority support",

  "admin.title": "Admin",
  "admin.lead": "Overview of all users, plans and activity.",
  "admin.users_total": "Total users",
  "admin.users_active": "Active",
  "admin.emails_today": "Emails today",
  "admin.emails_total": "Emails total",
  "admin.users": "Users",
  "admin.search": "Search by email or name…",
  "admin.col_name": "Name",
  "admin.col_plan": "Plan",
  "admin.col_today": "Today",
  "admin.col_total": "Total",
  "admin.col_created": "Created",
};

const DICTS: Record<Lang, Dict> = { de, en };

export function translator(lang: Lang) {
  const dict = DICTS[lang] ?? de;
  return (key: string, vars?: Record<string, string | number>): string => {
    let s = dict[key] ?? de[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.replace(`{${k}}`, String(v));
      }
    }
    return s;
  };
}

export type T = ReturnType<typeof translator>;
